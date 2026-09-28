"""
Long-polling runner: the bot, live in MAX, without needing a public HTTPS address.

Can also run on an always-on host. Do not run it alongside a webhook receiver
or another polling process for the same bot.

    export MAX_BOT_TOKEN=...
    python3 backend/runner.py
"""

from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.catalog import build_source  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import Store  # noqa: E402
from app.dialog import Dialog  # noqa: E402
from app.delivery import Delivery  # noqa: E402
from app.max_client import MaxClient  # noqa: E402
from app.process_control import shutdown_event  # noqa: E402

_level = logging.DEBUG if os.getenv("BOT_DEBUG") else logging.INFO
logging.basicConfig(level=_level, format="%(asctime)s %(levelname)s %(message)s")
# httpx logs every request at INFO, which drowns our own lines.
for _noisy in ("httpx", "httpcore", "hpack"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
log = logging.getLogger("runner")


def blocking_reason(client, has_token: bool) -> str | None:
    """
    Why this process must not poll, or None if it may.

    A function rather than a branch inside the loop so the decision can be tested
    without starting one. Two cases, and the second is the dangerous one: MAX hands
    each update to a single consumer, so a poller running beside a registered
    webhook does not duplicate traffic — it takes a random share of it and the bot
    answers roughly every other message.
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

    Only used with --service, where this process is a container in the default
    stack. Exiting non-zero would crash-loop and bury the cause in restart noise;
    exiting zero would look like it had finished. Idling keeps the reason visible
    in `docker compose logs polling` and leaves the API and UI running.
    """
    log.warning("%s — not polling. Fix the cause and restart this service.", reason)
    while True:
        time.sleep(3600)


def poll_updates(client, delivery, stop) -> None:
    while not stop.is_set():
        messages = client.get_updates()
        if not messages:
            # Invalid responses may return immediately; do not spin on them.
            stop.wait(1)
            continue
        for message in messages:
            for attempt in range(3):
                if stop.is_set():
                    return
                try:
                    if delivery.handle(message):
                        break
                except Exception:
                    log.exception("update processing failed")
                if attempt < 2 and stop.wait(2 ** attempt):
                    return
            else:
                # Keep the receipt unsent. One blocked chat must not stop the bot.
                log.error("Delivery exhausted; skipping this update without marking it sent")
            if stop.is_set():
                return


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
    blocked: str | None = None
    with shutdown_event() as stop, closing(Store(root / settings.db_path)) as store:
        with closing(MaxClient(settings.max_bot_token, settings.max_api_base,
                               mini_app_bot=settings.mini_app_bot)) as client:
            delivery = Delivery(Dialog(source, store), store, client)
            log.info(
                "catalogue: %d events (%s)",
                len(source.all_events()),
                "SYNTHETIC" if source.is_synthetic else "live",
            )
            blocked = blocking_reason(client, settings.has_max_token)
            if not blocked:
                log.info("polling %s", settings.max_api_base)
                poll_updates(client, delivery, stop)
                log.info("stopping")

    # Idle only after the database and HTTP client are closed: a service that sits
    # here for hours should not be holding either open.
    if blocked:
        if service:
            _idle(blocked)
        log.error("%s. Polling would steal a random share of its updates.", blocked)
        raise SystemExit(1)



if __name__ == "__main__":
    main()
