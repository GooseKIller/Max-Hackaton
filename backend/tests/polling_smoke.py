"""Exercise the real polling process against a local MAX substitute.

Run with compose.polling.yaml and backend/tests/compose.polling-test.yaml.
Only the substitute API is contacted. The server never downloads image URLs.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sqlite3
import sys
from threading import Condition
import time
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


USER_ID = "88101"
CHAT_ID = 88102
AUTH = "local-smoke-only"
BASE = os.environ.get("MAX_API_BASE", "http://fake-max:8080").rstrip("/")
DB_PATH = os.environ.get("DB_PATH", "/srv/state/app.db")
STATE = {"updates": [], "messages": [], "answers": [], "first_polls": 0,
         "checkpoint": None}
CHANGED = Condition()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def respond(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        if self.headers.get("Authorization") == AUTH:
            return True
        self.respond({"error": "unexpected test credentials"}, 403)
        return False

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/health":
            return self.respond({"ok": True})
        if url.path == "/test/state":
            with CHANGED:
                return self.respond(STATE)
        if url.path != "/updates":
            return self.respond({"error": "unknown path"}, 404)
        if not self.authorized():
            return
        params = parse_qs(url.query)
        marker = int(params.get("marker", ["0"])[0])
        with CHANGED:
            if "marker" not in params:
                STATE["first_polls"] += 1
            if marker >= len(STATE["updates"]):
                CHANGED.wait(timeout=1)
            self.respond({"updates": STATE["updates"][marker:],
                          "marker": len(STATE["updates"])})

    def do_POST(self):
        url = urlparse(self.path)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        with CHANGED:
            if url.path == "/test/update":
                STATE["updates"].append(body)
                CHANGED.notify_all()
            elif url.path == "/test/checkpoint":
                STATE["checkpoint"] = body
            elif url.path == "/messages":
                if not self.authorized():
                    return
                STATE["messages"].append({"query": parse_qs(url.query), "body": body})
            elif url.path == "/answers":
                if not self.authorized():
                    return
                if body != {"notification": ""}:
                    return self.respond({"error": "callback acknowledgement body"}, 400)
                STATE["answers"].append(parse_qs(url.query)["callback_id"][0])
            else:
                return self.respond({"error": "unknown path"}, 404)
            self.respond({"success": True})


def request(path, body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode()
    req = Request(BASE + path, data=data, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=5) as response:
        return json.load(response)


def wait_for(check, label):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(0.1)
    raise AssertionError("Timed out: " + label)


def wait_state(check, label):
    def ready():
        state = request("/test/state")
        return state if check(state) else None
    return wait_for(ready, label)


def message(text, identity):
    return {"update_type": "message_created", "message": {
        "sender": {"user_id": int(USER_ID)}, "recipient": {"chat_id": CHAT_ID},
        "body": {"text": text, "mid": identity}}}


def callback(text, identity):
    return {"update_type": "message_callback", "callback": {
        "user": {"user_id": int(USER_ID)}, "callback_id": identity, "payload": text},
        "message": {"recipient": {"chat_id": CHAT_ID}}}


def send(update, expected):
    before = len(request("/test/state")["messages"])
    request("/test/update", update)
    state = wait_state(lambda s: len(s["messages"]) > before, "bot reply")
    assert len(state["messages"]) == before + 1, "Unexpected duplicate bot reply"
    reply = state["messages"][-1]
    assert reply["query"] == {"chat_id": [str(CHAT_ID)]}
    assert expected in reply["body"]["text"], reply["body"]["text"]
    cb = update.get("callback", {}).get("callback_id")
    if cb:
        assert cb in state["answers"], "Missing callback acknowledgement"
    return reply["body"]


def db_snapshot():
    with sqlite3.connect(DB_PATH, timeout=5) as db:
        db.row_factory = sqlite3.Row
        user = db.execute("SELECT * FROM users WHERE user_id = ?", (USER_ID,)).fetchone()
        session = db.execute("SELECT * FROM sessions WHERE user_id = ?", (USER_ID,)).fetchone()
        pref = db.execute("SELECT opted_in FROM reminder_prefs WHERE user_id = ?",
                          (USER_ID,)).fetchone()
        interactions = db.execute("SELECT COUNT(*) FROM interactions WHERE user_id = ?",
                                  (USER_ID,)).fetchone()[0]
        likes = db.execute("SELECT COUNT(*) FROM interactions WHERE user_id = ? AND signal = 'like'",
                          (USER_ID,)).fetchone()[0]
        pending = db.execute("SELECT COUNT(*) FROM update_receipts WHERE sent = 0").fetchone()[0]
    return {"user": dict(user) if user else None, "session": dict(session) if session else None,
            "opted_in": pref[0] if pref else 0, "interactions": interactions,
            "likes": likes, "pending": pending}


def settled():
    def ready():
        snapshot = db_snapshot()
        return snapshot if snapshot["pending"] == 0 else None
    return wait_for(ready, "durable delivery receipt")


def flow():
    send(message("/start", "start"), "Сколько тебе лет?")
    send(callback("18", "age"), "Сколько осталось на карте?")
    card = send(message("3000", "balance"), "Смотри, что есть")
    buttons = [b["text"] for attachment in card.get("attachments", [])
               if attachment["type"] == "inline_keyboard"
               for row in attachment["payload"]["buttons"] for b in row]
    assert "❤️ пойду" in buttons and "настройки" in buttons
    send(callback("❤️ пойду", "like"), "Записал.")
    send(message("/plan", "plan"), "Итого")
    send(message("/reminders", "reminders"), "Напоминания выключены.")
    send(callback("Включить напоминания", "opt-in"), "Напоминания включены.")
    snapshot = settled()
    assert snapshot["user"]["age"] == 18 and snapshot["user"]["balance_general"] == 3000
    assert snapshot["opted_in"] == 1 and snapshot["likes"] == 1
    state = request("/test/state")
    request("/test/checkpoint", {"db": snapshot, "messages": len(state["messages"]),
                                 "first_polls": state["first_polls"]})
    print("PASS: onboarding, event card, reaction, budget plan and reminder opt-in")


def after_restart():
    checkpoint = request("/test/state")["checkpoint"]
    assert checkpoint, "Run flow first"
    wait_for(lambda: request("/test/state")["first_polls"] > checkpoint["first_polls"],
             "new polling process")
    # The substitute replays all updates on a new polling session. A duplicate
    # reaction is also sent explicitly; both must leave the stored dialog intact.
    before = request("/test/state")["answers"].count("like")
    request("/test/update", callback("❤️ пойду", "like"))
    wait_for(lambda: request("/test/state")["answers"].count("like") > before,
             "replayed callback acknowledgement")
    send(message("/reminders", "restart-barrier"), "Напоминания включены.")
    assert settled() == checkpoint["db"], "Restart/replay changed the profile or dialog"
    assert len(request("/test/state")["messages"]) == checkpoint["messages"] + 1
    print("PASS: profile and consent persist; replayed callback does not advance the dialog")


def reminder():
    # Only this test harness injects a date. Production CLI and scheduler keep
    # the real clock. MaxSender still makes a real HTTP request to the substitute.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from backend.app.db import Store
    from backend.app.reminder_worker import MaxSender
    from backend.app.reminders import MSK, run_once

    store = Store(DB_PATH)
    sender = MaxSender(AUTH, BASE)
    now = datetime(2026, 12, 17, 12, tzinfo=MSK)
    before = len(request("/test/state")["messages"])
    try:
        assert store.is_opted_in(USER_ID), "Consent was not shared with the worker"
        assert run_once(store, sender, now) == {"sent": 1, "failed": 0}
        sent = request("/test/state")["messages"]
        assert len(sent) == before + 1
        assert sent[-1]["query"] == {"user_id": [USER_ID]}
        assert "14 дней" in sent[-1]["body"]["text"]
        assert "3000" in sent[-1]["body"]["text"]
        assert run_once(store, sender, now) == {"sent": 0, "failed": 0}
        assert len(request("/test/state")["messages"]) == before + 1
        send(callback("Отключить напоминания", "opt-out"), "Напоминания отключены.")
        assert not store.is_opted_in(USER_ID)
        before = len(request("/test/state")["messages"])
        assert run_once(store, sender, now.replace(day=29)) == {"sent": 0, "failed": 0}
        assert len(request("/test/state")["messages"]) == before
    finally:
        sender.close()
        store.close()
    print("PASS: worker HTTP delivery, duplicate prevention and opt-out on the shared database")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["server", "flow", "after-restart", "reminder"])
    args = parser.parse_args()
    if urlparse(BASE).hostname not in {"fake-max", "localhost", "127.0.0.1"}:
        raise SystemExit("Smoke checks only allow the isolated test API")
    if args.mode == "server":
        ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
    else:
        {"flow": flow, "after-restart": after_restart, "reminder": reminder}[args.mode]()
