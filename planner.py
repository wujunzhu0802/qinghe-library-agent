"""本地模拟预约。每个时段代表演示日的一小时，容量冲突在数据库内处理。"""
import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
SLOTS = ("09:00", "14:00", "19:00")
BLOCKED = {("S01", "14:00"), ("S02", "09:00")}
DB = ROOT / "reservations.sqlite3"
SHANGHAI = timezone(timedelta(hours=8))


def today():
    return datetime.now(SHANGHAI).date().isoformat()


def date_value(day=None):
    day = today() if day is None else day
    try:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError("请选择有效日期。") from None
    return day


def period(day, slot):
    return f"{date_value(day)} {slot}"



@contextmanager
def connect():
    with closing(sqlite3.connect(DB)) as con, con:
        con.execute("""CREATE TABLE IF NOT EXISTS reservations (
            id TEXT PRIMARY KEY, session TEXT NOT NULL, space TEXT NOT NULL,
            slot TEXT NOT NULL, seats INTEGER NOT NULL, UNIQUE(space, slot))""")
        con.execute("""CREATE TABLE IF NOT EXISTS waiting (
            seq INTEGER PRIMARY KEY AUTOINCREMENT, session TEXT NOT NULL,
            space TEXT NOT NULL, slot TEXT NOT NULL, seats INTEGER NOT NULL,
            UNIQUE(session, space, slot))""")
        con.execute("CREATE TABLE IF NOT EXISTS checkins (id TEXT PRIMARY KEY)")
        con.execute("""CREATE TABLE IF NOT EXISTS activity (
            seq INTEGER PRIMARY KEY AUTOINCREMENT, session TEXT NOT NULL,
            kind TEXT NOT NULL, space TEXT NOT NULL, slot TEXT NOT NULL, at TEXT NOT NULL)""")
        if con.execute("PRAGMA user_version").fetchone()[0] < 1:
            con.execute("BEGIN IMMEDIATE")
            if con.execute("PRAGMA user_version").fetchone()[0] < 1:
                for table in ("reservations", "waiting", "activity"):
                    con.execute(f"UPDATE {table} SET slot=? || ' ' || slot WHERE length(slot)=5", (today(),))
                con.execute("PRAGMA user_version=1")
            con.commit()
        yield con


def available(seats, discussion, slot, day=None):
    if type(seats) is not int or not 1 <= seats <= 99 or type(discussion) is not bool or slot not in SLOTS:
        raise ValueError("请选择有效的人数、用途和时段。")
    key = period(day, slot)
    with connect() as con:
        taken = set(con.execute("SELECT space, slot FROM reservations"))
    return [dict(s, available=(s["id"], slot) not in BLOCKED and (s["id"], key) not in taken,
                 waitlist=(s["id"], key) in taken, day=key[:10], slot=slot)
            for s in DATA["spaces"] if s["seats"] >= seats and s["discussion"] == discussion]


def reserve(session, space, slot, seats, discussion, day=None):
    choices = available(seats, discussion, slot, day)
    slot = period(day, slot)
    if not any(s["id"] == space and s["available"] for s in choices):
        raise ValueError("该场地已占用或不符合条件，请重新查询。")
    ref = uuid4().hex
    try:
        with connect() as con:
            con.execute("INSERT INTO reservations VALUES (?, ?, ?, ?, ?)", (ref, session, space, slot, seats))
            log(con, session, "预约成功", space, slot)
    except sqlite3.IntegrityError as error:
        raise ValueError("此时段刚被占用，请重新查询。") from error
    return bookings(session)


def bookings(session):
    with connect() as con:
        rows = con.execute("""SELECT r.id, r.space, r.slot, r.seats, c.id IS NOT NULL
            FROM reservations r LEFT JOIN checkins c ON c.id=r.id WHERE r.session=? ORDER BY r.slot""", (session,))
        names = {s["id"]: s["name"] for s in DATA["spaces"]}
        return [dict(id=ref, space=names[space], day=slot[:10], slot=slot[11:], seats=seats, checked_in=bool(checked)) for ref, space, slot, seats, checked in rows]


def cancel(session, ref):
    return release(session, ref, False)


def release(session, ref, checked_out):
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        space, slot = owned(con, session, ref)
        checked = con.execute("SELECT 1 FROM checkins WHERE id=?", (ref,)).fetchone()
        if bool(checked) != checked_out:
            raise ValueError("签到后的预约请使用结束使用。" if checked else "请先签到。")
        con.execute("DELETE FROM reservations WHERE id=?", (ref,))
        con.execute("DELETE FROM checkins WHERE id=?", (ref,))
        log(con, session, "结束使用" if checked_out else "取消预约", space, slot)
        promote(con, space, slot)
    return bookings(session)


def schedule(day=None):
    day = date_value(day)
    with connect() as con:
        occupied = set(con.execute("SELECT space, slot FROM reservations"))
    return {"day": day, "slots": SLOTS, "spaces": [
        dict(space, free={slot: (space["id"], slot) not in BLOCKED and (space["id"], period(day, slot)) not in occupied for slot in SLOTS})
        for space in DATA["spaces"]
    ]}


def reschedule(session, ref, slot, day=None):
    if slot not in SLOTS:
        raise ValueError("请选择有效时段。")
    slot = period(day, slot)
    try:
        with connect() as con:
            con.execute("BEGIN IMMEDIATE")
            space, old_slot = owned(con, session, ref)
            if con.execute("SELECT 1 FROM checkins WHERE id=?", (ref,)).fetchone():
                raise ValueError("已签到的预约不能改期。")
            if slot == old_slot:
                raise ValueError("请选择不同的时段。")
            if (space, slot[11:]) in BLOCKED:
                raise ValueError("目标时段已占用，原预约已保留。")
            con.execute("UPDATE reservations SET slot=? WHERE id=? AND session=?", (slot, ref, session))
            con.execute("DELETE FROM waiting WHERE session=? AND space=? AND slot=?", (session, space, slot))
            log(con, session, "改期成功", space, slot)
            promote(con, space, old_slot)
    except sqlite3.IntegrityError as error:
        raise ValueError("目标时段已占用，原预约已保留。") from error
    return bookings(session)


def owned(con, session, ref):
    row = con.execute("SELECT space, slot FROM reservations WHERE id=? AND session=?", (ref, session)).fetchone()
    if not row:
        raise ValueError("预约不存在或已取消。")
    return row


def log(con, session, kind, space, slot):
    at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    con.execute("INSERT INTO activity (session,kind,space,slot,at) VALUES (?,?,?,?,?)",
                (session, kind, space, slot, at))


def promote(con, space, slot):
    next_user = con.execute("""SELECT seq, session, seats FROM waiting
        WHERE space=? AND slot=? ORDER BY seq LIMIT 1""", (space, slot)).fetchone()
    if next_user:
        seq, session, seats = next_user
        con.execute("INSERT INTO reservations VALUES (?,?,?,?,?)", (uuid4().hex, session, space, slot, seats))
        con.execute("DELETE FROM waiting WHERE seq=?", (seq,))
        log(con, session, "候补转正", space, slot)


def join_waiting(session, space, slot, seats, discussion, day=None):
    options = available(seats, discussion, slot, day)
    if not any(s["id"] == space for s in options) or (space, slot) in BLOCKED:
        raise ValueError("该场地或时段不开放候补。")
    slot = period(day, slot)
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        owner = con.execute("SELECT session FROM reservations WHERE space=? AND slot=?", (space, slot)).fetchone()
        if not owner:
            raise ValueError("该时段已释放，请直接预约。")
        if owner[0] == session:
            raise ValueError("你已经预约了该时段。")
        changed = con.execute("""INSERT OR IGNORE INTO waiting (session,space,slot,seats)
            VALUES (?,?,?,?)""", (session, space, slot, seats)).rowcount
        if changed:
            log(con, session, "加入候补", space, slot)
    return queue(session)


def queue(session):
    with connect() as con:
        rows = con.execute("""SELECT w.seq,w.space,w.slot,
            (SELECT COUNT(*) FROM waiting ahead WHERE ahead.space=w.space AND ahead.slot=w.slot AND ahead.seq<=w.seq)
            FROM waiting w WHERE session=? ORDER BY w.seq""", (session,))
        return [dict(id=seq, space=names(space), day=slot[:10], slot=slot[11:], position=position)
                for seq, space, slot, position in rows]


def withdraw(session, ref):
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT space, slot FROM waiting WHERE seq=? AND session=?", (ref, session)).fetchone()
        if not row:
            raise ValueError("候补已结束，请刷新。")
        con.execute("DELETE FROM waiting WHERE seq=? AND session=?", (ref, session))
        log(con, session, "退出候补", *row)
    return queue(session)


def check_in(session, ref):
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        space, slot = owned(con, session, ref)
        if con.execute("INSERT OR IGNORE INTO checkins VALUES (?)", (ref,)).rowcount:
            log(con, session, "模拟签到", space, slot)
    return bookings(session)


def names(space):
    return next(s["name"] for s in DATA["spaces"] if s["id"] == space)


def history(session):
    with connect() as con:
        rows = con.execute("""SELECT kind,space,slot,at FROM activity WHERE session=?
            ORDER BY seq DESC LIMIT 60""", (session,))
        return [dict(kind=kind, space=names(space), day=slot[:10], slot=slot[11:], at=at) for kind, space, slot, at in rows]
