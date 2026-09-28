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


def main() -> None:
    if not settings.has_max_token:
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
    with shutdown_event() as stop, closing(Store(root / settings.db_path)) as store:
        with closing(MaxClient(settings.max_bot_token, settings.max_api_base,
                               mini_app_bot=settings.mini_app_bot)) as client:
            delivery = Delivery(Dialog(source, store), store, client)
            log.info(
                "catalogue: %d events (%s)",
                len(source.all_events()),
                "SYNTHETIC" if source.is_synthetic else "live",
            )
            log.info("polling %s", settings.max_api_base)
            poll_updates(client, delivery, stop)
            log.info("stopping")


if __name__ == "__main__":
    main()
