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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.catalog import build_source  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import Store  # noqa: E402
from app.dialog import Dialog  # noqa: E402
from app.max_client import MaxClient  # noqa: E402

_level = logging.DEBUG if os.getenv("BOT_DEBUG") else logging.INFO
logging.basicConfig(level=_level, format="%(asctime)s %(levelname)s %(message)s")
# httpx logs every request at INFO, which drowns our own lines.
for _noisy in ("httpx", "httpcore", "hpack"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
log = logging.getLogger("runner")


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
    store = Store(root / settings.db_path)
    dialog = Dialog(source, store)
    client = MaxClient(settings.max_bot_token, settings.max_api_base)

    log.info(
        "catalogue: %d events (%s)",
        len(source.all_events()),
        "SYNTHETIC" if source.is_synthetic else "live",
    )
    log.info("polling %s", settings.max_api_base)

    try:
        while True:
            for message in client.get_updates():
                log.info("<- %s: %s", message.user_id, message.text[:60])
                try:
                    reply = dialog.handle(message.user_id, message.text)
                except Exception:
                    # One bad message must not stop the bot. The user can continue
                    # after an error without a restart — a scored criterion.
                    log.exception("dialog failed for %s", message.user_id)
                    continue
                if message.callback_id:
                    client.answer_callback(message.callback_id)
                client.send_message(message.chat_id, reply.text, reply.buttons, reply.image_url)
    except KeyboardInterrupt:
        log.info("stopping")
    finally:
        client.close()


if __name__ == "__main__":
    main()
