"""
The first thing to run when a MAX bot token arrives.

Four things in `app/max_client.py` are written from the documentation and have never
touched a live token. This checks all of them in one pass and prints what actually
works, so the unknowns are resolved in minutes rather than by guesswork at 2am.

  1. Does the token work at all?                       GET /me
  2. Does long polling return the shape we expect?     GET /updates
  3. Does our inline-keyboard payload get accepted?    POST /messages
  4. Can the bot send proactively, unprompted?         POST /messages to a known chat

Question 4 matters most: the whole expiry-reminder feature, and our candidate for the
+0.15 platform bonus, depends on the answer being yes.

    export MAX_BOT_TOKEN=...
    python3 backend/probe_max.py                # checks 1 and 2
    python3 backend/probe_max.py --chat 12345   # also checks 3 and 4
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx  # noqa: E402

from app.config import settings, ssl_context  # noqa: E402
from app.max_client import parse_update  # noqa: E402

OK = "  OK  "
FAIL = " FAIL "
WARN = " WARN "


def line(status: str, text: str) -> None:
    print(f"[{status}] {text}")


def call(method: str, path: str, **kw) -> tuple[int, object]:
    url = f"{settings.max_api_base}{path}"
    r = httpx.request(
        method,
        url,
        headers={"Authorization": settings.max_bot_token},
        timeout=kw.pop("timeout", 30.0),
        verify=ssl_context(),
        **kw,
    )
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text[:300]


def probe_me() -> bool:
    print("\n1. Token and identity — GET /me")
    try:
        status, body = call("GET", "/me")
    except httpx.HTTPError as exc:
        line(FAIL, f"request failed: {exc}")
        return False

    if status != 200:
        line(FAIL, f"HTTP {status}: {body}")
        if status == 401:
            print("       The token is wrong, expired or revoked.")
        if status == 404:
            print("       MAX_API_BASE may be wrong — re-check dev.max.ru/docs-api.")
        return False

    line(OK, f"@{body.get('username')} · id={body.get('user_id')} · is_bot={body.get('is_bot')}")
    return True


def probe_updates(seconds: int) -> None:
    print(f"\n2. Long polling — GET /updates (waiting up to {seconds}s)")
    print(f"       Send the bot a message now, and press a button if you can.")
    try:
        status, body = call(
            "GET", "/updates", params={"timeout": seconds}, timeout=seconds + 10
        )
    except httpx.HTTPError as exc:
        line(FAIL, f"request failed: {exc}")
        return

    if status != 200:
        line(FAIL, f"HTTP {status}: {body}")
        return

    updates = body.get("updates", []) if isinstance(body, dict) else []
    marker = body.get("marker") if isinstance(body, dict) else None
    line(OK, f"HTTP 200, marker={marker}, {len(updates)} update(s)")

    if not updates:
        line(WARN, "nothing arrived — send the bot a message and run this again")
        return

    for u in updates:
        kind = u.get("update_type") or u.get("type")
        parsed = parse_update(u)
        if parsed:
            line(OK, f"'{kind}' parsed -> user={parsed.user_id} chat={parsed.chat_id} "
                     f"text={parsed.text[:40]!r}")
        else:
            line(FAIL, f"'{kind}' NOT parsed by parse_update — shape below")
            print(json.dumps(u, ensure_ascii=False, indent=2)[:1200])
            print("       Fix parse_update() in app/max_client.py to match this.")


def probe_send(chat_id: int) -> None:
    print(f"\n3. Plain message — POST /messages to chat {chat_id}")
    try:
        status, body = call(
            "POST", "/messages",
            params={"chat_id": chat_id},
            json={"text": "Проверка связи. Это тестовое сообщение."},
        )
    except httpx.HTTPError as exc:
        line(FAIL, f"request failed: {exc}")
        return
    if status in (200, 201):
        line(OK, "plain text delivered")
    else:
        line(FAIL, f"HTTP {status}: {body}")
        return

    print("\n4. Inline keyboard — the payload shape we guessed from the docs")
    payload = {
        "text": "Кнопки работают?",
        "attachments": [
            {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": [
                        [{"type": "callback", "text": "да", "payload": "да"}],
                        [{"type": "callback", "text": "нет", "payload": "нет"}],
                    ]
                },
            }
        ],
    }
    try:
        status, body = call("POST", "/messages", params={"chat_id": chat_id}, json=payload)
    except httpx.HTTPError as exc:
        line(FAIL, f"request failed: {exc}")
        return

    if status in (200, 201):
        line(OK, "keyboard accepted — check it renders correctly in the app")
    else:
        line(FAIL, f"HTTP {status}: {body}")
        print("       Our guessed shape is wrong. Correct send_message() in")
        print("       app/max_client.py against the current docs. This is the one")
        print("       place the wrong shape is isolated to.")


def probe_proactive(chat_id: int) -> None:
    print("\n5. Proactive send — unprompted, 5s after the last message")
    print("       The expiry reminder and our platform-bonus candidate depend on this.")
    time.sleep(5)
    try:
        status, body = call(
            "POST", "/messages",
            params={"chat_id": chat_id},
            json={"text": "Это сообщение отправлено ботом по своей инициативе."},
        )
    except httpx.HTTPError as exc:
        line(FAIL, f"request failed: {exc}")
        return

    if status in (200, 201):
        line(OK, "proactive send works — reminders are feasible")
    else:
        line(FAIL, f"HTTP {status}: {body}")
        print("       If proactive sends are blocked, the reminder must become a")
        print("       pull ('сколько осталось') instead of a push, and the platform")
        print("       bonus needs a different candidate.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chat", type=int, help="chat_id to send test messages to")
    ap.add_argument("--wait", type=int, default=30, help="long-poll seconds (default 30)")
    args = ap.parse_args()

    if not settings.has_max_token:
        print("MAX_BOT_TOKEN is not set. Put it in .env (see .env.example).")
        print("Waiting on the organizers? See docs/testing-in-max.md")
        return 1

    print(f"MAX_API_BASE = {settings.max_api_base}")

    if not probe_me():
        print("\nStopping: nothing else can work until the token does.")
        return 1

    probe_updates(args.wait)

    if args.chat:
        probe_send(args.chat)
        probe_proactive(args.chat)
    else:
        print("\n3-5. Skipped — rerun with --chat <id> to test sending.")
        print("     Get the id from the 'chat=' value printed in step 2.")

    print("\nRecord the answers in docs/testing-in-max.md, then:  python3 backend/runner.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
