"""
The reminder scheduler process.

Runs `reminders.run_once` on a timer. Deliberately its own entry point, not wired
into the polling loop, so it can be run, tested and demonstrated on its own and so it
does not touch the MAX receive code the bot owner maintains.

    python -m app.reminder_worker --once            # one pass, then exit
    python -m app.reminder_worker --loop            # every hour
    python -m app.reminder_worker --once --dry-run  # print instead of sending

Sending goes straight to the MAX REST API by `user_id` (a proactive message into the
person's dialog with the bot), reusing the same TLS trust and token as the rest of the
app. It does not import the bot's MaxClient, to keep this contribution isolated while
the MAX integration is still being hardened — the two can be merged later behind one
HTTP client if the team prefers.
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime
from pathlib import Path

from .config import settings
from .db import Store
from .reminders import MSK, Reminder, due, run_once

log = logging.getLogger(__name__)

# One dialog allows two messages per second; a proactive batch is well under any per-
# dialog limit, but stay polite against the shared API budget on large runs.
_MIN_GAP_SECONDS = 0.1
LOOP_EVERY_SECONDS = 3600


class MaxSender:
    """Delivers a reminder as a proactive message to a user's dialog with the bot."""

    def __init__(self, token: str, base_url: str):
        import httpx

        from .config import ssl_context

        if not token:
            raise ValueError("MAX_BOT_TOKEN is empty — cannot send reminders")
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": token},
            timeout=30.0,
            verify=ssl_context(),
        )

    def __call__(self, reminder: Reminder) -> bool:
        keyboard = {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [{"type": "callback", "text": b, "payload": b}]
                    for b in reminder.buttons
                ]
            },
        }
        try:
            r = self._client.post(
                "/messages",
                params={"user_id": reminder.user_id},
                json={"text": reminder.text, "attachments": [keyboard]},
            )
        except Exception as exc:  # noqa: BLE001 — a failed send must not kill the loop
            log.warning("reminder send failed for %s: %s", reminder.user_id, exc)
            return False
        if r.status_code < 400:
            return True
        log.warning(
            "reminder send HTTP %s for %s: %s",
            r.status_code, reminder.user_id, r.text[:160],
        )
        return False

    def close(self) -> None:
        self._client.close()


def _dry_run(reminder: Reminder) -> bool:
    print(f"[{reminder.rule_key}] -> {reminder.user_id}\n  {reminder.text}\n  {reminder.buttons}")
    return True


def _pass(store: Store, send) -> dict:
    def throttled(reminder: Reminder) -> bool:
        ok = send(reminder)
        time.sleep(_MIN_GAP_SECONDS)
        return ok

    result = run_once(store, throttled)
    log.info("reminder pass: sent=%s failed=%s", result["sent"], result["failed"])
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Pushkin Card reminder scheduler")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="run one pass and exit")
    mode.add_argument("--loop", action="store_true", help="run every hour")
    parser.add_argument(
        "--dry-run", action="store_true", help="print reminders instead of sending"
    )
    parser.add_argument("--preview-at", help="ISO datetime for dry-run only; never send with a fake date")
    args = parser.parse_args()
    preview_at = None
    if args.preview_at:
        if not args.dry_run:
            parser.error("--preview-at requires --dry-run")
        try:
            preview_at = datetime.fromisoformat(args.preview_at)
            if preview_at.tzinfo is None:
                preview_at = preview_at.replace(tzinfo=MSK)
        except ValueError:
            parser.error("Invalid ISO datetime")

    store = Store(Path(__file__).resolve().parents[2] / settings.db_path)
    send = _dry_run if args.dry_run else MaxSender(settings.max_bot_token, settings.max_api_base)

    try:
        if args.dry_run:
            for reminder in due(store, preview_at) if preview_at else due(store):
                _dry_run(reminder)
            return  # Preview must not claim or mark any deliveries.
        if args.once:
            _pass(store, send)
        else:
            while True:
                _pass(store, send)
                time.sleep(LOOP_EVERY_SECONDS)
    finally:
        if hasattr(send, "close"):
            send.close()
        store.close()


if __name__ == "__main__":
    main()
