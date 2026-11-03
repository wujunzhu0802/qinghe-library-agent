"""本地模拟预约。每个时段代表演示日的一小时，容量冲突在数据库内处理。"""
import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
SLOTS = ("09:00", "14:00", "19:00")
BLOCKED = {("S01", "14:00"), ("S02", "09:00")}
DB = ROOT / "reservations.sqlite3"


@contextmanager
def connect():
    with closing(sqlite3.connect(DB)) as con, con:
        con.execute("""CREATE TABLE IF NOT EXISTS reservations (
            id TEXT PRIMARY KEY, session TEXT NOT NULL, space TEXT NOT NULL,
            slot TEXT NOT NULL, seats INTEGER NOT NULL, UNIQUE(space, slot))""")
        yield con


def available(seats, discussion, slot):
    if type(seats) is not int or not 1 <= seats <= 99 or type(discussion) is not bool or slot not in SLOTS:
        raise ValueError("请选择有效的人数、用途和时段。")
    with connect() as con:
        taken = set(con.execute("SELECT space, slot FROM reservations"))
    return [dict(s, available=(s["id"], slot) not in BLOCKED | taken, slot=slot)
            for s in DATA["spaces"] if s["seats"] >= seats and s["discussion"] == discussion]


def reserve(session, space, slot, seats, discussion):
    choices = available(seats, discussion, slot)
    if not any(s["id"] == space and s["available"] for s in choices):
        raise ValueError("该场地已占用或不符合条件，请重新查询。")
    ref = uuid4().hex
    try:
        with connect() as con:
            con.execute("INSERT INTO reservations VALUES (?, ?, ?, ?, ?)", (ref, session, space, slot, seats))
    except sqlite3.IntegrityError as error:
        raise ValueError("此时段刚被占用，请重新查询。") from error
    return bookings(session)


def bookings(session):
    with connect() as con:
        rows = con.execute("SELECT id, space, slot, seats FROM reservations WHERE session=? ORDER BY slot", (session,))
        names = {s["id"]: s["name"] for s in DATA["spaces"]}
        return [dict(id=ref, space=names[space], slot=slot, seats=seats) for ref, space, slot, seats in rows]


def cancel(session, ref):
    with connect() as con:
        changed = con.execute("DELETE FROM reservations WHERE id=? AND session=?", (ref, session)).rowcount
    if not changed:
        raise ValueError("预约不存在或已取消。")
    return bookings(session)

def schedule():
    with connect() as con:
        occupied = BLOCKED | set(con.execute("SELECT space, slot FROM reservations"))
    return {"slots": SLOTS, "spaces": [
        dict(space, free={slot: (space["id"], slot) not in occupied for slot in SLOTS})
        for space in DATA["spaces"]
    ]}


def reschedule(session, ref, slot):
    if slot not in SLOTS:
        raise ValueError("请选择有效时段。")
    try:
        with connect() as con:
            old = con.execute("SELECT space, slot FROM reservations WHERE id=? AND session=?",
                              (ref, session)).fetchone()
            if not old:
                raise ValueError("预约不存在或已取消。")
            if (old[0], slot) in BLOCKED:
                raise ValueError("目标时段已占用，原预约已保留。")
            con.execute("UPDATE reservations SET slot=? WHERE id=? AND session=?", (slot, ref, session))
    except sqlite3.IntegrityError as error:
        raise ValueError("目标时段已占用，原预约已保留。") from error
    return bookings(session)
