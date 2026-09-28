"""
Long-polling runner: the bot, live in MAX, without needing a public HTTPS address.

Use this during development. The deployed version should use the webhook in
`app/main.py` instead.

    export MAX_BOT_TOKEN=...
    python3 backend/runner.py
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.catalog import build_source  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import Store  # noqa: E402
from app.dialog import Dialog  # noqa: E402
from app.delivery import Delivery  # noqa: E402
from app.max_client import MaxClient  # noqa: E402

_level = logging.DEBUG if os.getenv("BOT_DEBUG") else logging.INFO
logging.basicConfig(level=_level, format="%(asctime)s %(levelname)s %(message)s")
# httpx logs every request at INFO, which drowns our own lines.
for _noisy in ("httpx", "httpcore", "hpack"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
log = logging.getLogger("runner")


def blocking_reason(client, has_token: bool) -> str | None:
    """
    Why this process must not poll, or None if it may.

    Split out from the loop so the decision can be tested without starting one.
    Two cases, and the second is the dangerous one: MAX hands each update to a
    single consumer, so a poller running beside a registered webhook does not
    duplicate traffic — it takes a random share of it and the bot answers roughly
    every other message.
    """
    if not has_token:
        return "MAX_BOT_TOKEN is not set"
    subscriptions = client.list_subscriptions()
    if subscriptions:
        urls = ", ".join(str(sub.get("url", "?")) for sub in subscriptions)
        return f"a webhook is already registered ({urls})"
    return None


def _idle(reason: str) -> None:
    """
    Stay up, do nothing, say why.

    Only used with --service. A container that exits non-zero would crash-loop and
    bury the actual reason in restart noise; one that exits zero looks like it
    finished successfully. Idling keeps the reason on screen in `docker compose
    logs` and leaves the rest of the stack running.
    """
    log.warning("%s — not polling. Fix the cause and restart this service.", reason)
    while True:
        time.sleep(3600)


def main(argv: list[str] | None = None) -> None:
    service = "--service" in (argv if argv is not None else sys.argv[1:])

    if not settings.has_max_token:
        message = "MAX_BOT_TOKEN is not set"
        if service:
            _idle(f"{message}; the API and UI keep working without it")
        print("MAX_BOT_TOKEN is not set.")
        print("Copy .env.example to .env and put the token from the organizers there,")
        print("or try the conversation without MAX:  python3 backend/console.py")
        raise SystemExit(1)

    root = Path(__file__).resolve().parent.parent
    source = build_source(
        api_key=settings.proculture_api_key,
        subordinations=settings.proculture_subordinations or None,
        fixture_path=root / settings.catalog_path,
    )
    store = Store(root / settings.db_path)
    dialog = Dialog(source, store)
    client = MaxClient(settings.max_bot_token, settings.max_api_base, mini_app_bot=settings.mini_app_bot)
    delivery = Delivery(dialog, store, client)

    log.info(
        "catalogue: %d events (%s)",
        len(source.all_events()),
        "SYNTHETIC" if source.is_synthetic else "live",
    )
    blocked = blocking_reason(client, settings.has_max_token)
    if blocked:
        client.close()
        store.close()
        if service:
            _idle(blocked)
        log.error("%s. Polling would steal a random share of its updates.", blocked)
        raise SystemExit(1)

    log.info("polling %s", settings.max_api_base)

    try:
        while True:
            for message in client.get_updates():
                for attempt in range(3):
                    try:
                        if delivery.handle(message):
                            break
                    except Exception:
                        log.exception("update processing failed")
                    time.sleep(2 ** attempt)
                else:
                    log.error("Delivery exhausted; restart or webhook redelivery may be required")
    except KeyboardInterrupt:
        log.info("stopping")
    finally:
        client.close()
        store.close()


if __name__ == "__main__":
    main()
