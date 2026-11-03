"""启动：python app.py；浏览器访问 http://127.0.0.1:8765。"""
import argparse
import json
import os
import re
from planner import available, bookings, cancel, reserve
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError

from agent import ROOT, offline, online


def load_env():
    path = ROOT / ".env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL") and value.strip():
                os.environ.setdefault(key, value.strip())


class Handler(BaseHTTPRequestHandler):
    def send(self, code, data, kind="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", kind + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def reply(self, code, data):
        self.send(code, json.dumps(data, ensure_ascii=False).encode())

    def do_GET(self):
        if self.path in ("/", "/slides"):
            name = "demo.html" if self.path == "/" else "slides.html"
            self.send(200, (ROOT / name).read_bytes(), "text/html")
        else:
            self.reply(404, {"error": "页面不存在"})

    def do_POST(self):
        if self.path in ("/plan", "/book", "/bookings", "/cancel"):
            return self.planner_request()
        if self.path != "/ask":
            return self.reply(404, {"error": "接口不存在"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 8192:
                raise ValueError()
            body = json.loads(self.rfile.read(size))
            q = body["question"].strip()
            mode = body["mode"]
            if not 1 <= len(q) <= 600 or mode not in ("online", "offline"):
                raise ValueError()
        except (ValueError, KeyError, TypeError, AttributeError):
            return self.reply(400, {"error": "请输入 1–600 字，并选择模式。"})
        trace = []
        if mode == "online":
            if not os.getenv("OPENAI_API_KEY"):
                return self.reply(503, {"error": "未配置 API Key。请使用离线演练，或配置后重启。"})
            try:
                answer = online(q, trace)
            except (URLError, TimeoutError, KeyError, ValueError, TypeError, IndexError, OSError):
                return self.reply(502, {"error": "模型调用失败。请检查网络、模型名和 API 配置，或切到离线演练。", "trace": trace})
        else:
            answer = offline(q, trace)
        self.reply(200, {"answer": answer, "trace": trace, "mode": mode, "follow_up": not trace and ("人数" in answer or "几人" in answer or "几位" in answer)})

    def planner_request(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 8192:
                raise ValueError("请求格式错误。")
            body = json.loads(self.rfile.read(size))
            session = body.get("session", "")
            if not re.fullmatch(r"[a-f0-9-]{36}", session):
                raise ValueError("会话无效，请刷新网页。")
            if self.path == "/bookings":
                result = bookings(session)
            elif self.path == "/cancel":
                result = cancel(session, body["id"])
            else:
                args = [body["seats"], body["discussion"], body["slot"]]
                result = available(*args) if self.path == "/plan" else reserve(
                    session, body["space"], args[2], args[0], args[1])
            self.reply(200, {"items": result})
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            self.reply(400, {"error": str(exc) if isinstance(exc, ValueError) else "请求格式错误。"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    load_env()
    print(f"打开 http://127.0.0.1:{args.port}", flush=True)
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        server.serve_forever()
