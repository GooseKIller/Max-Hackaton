"""
The service.

FastAPI serves two things:
  - /health, so Docker and a judge can see it is alive
  - /webhook, for MAX to post updates to once the bot is deployed

For local development there is also a long-polling runner in `runner.py`, which needs
no public HTTPS.

Note for the submission: FastAPI publishes an OpenAPI 3.1 document at /openapi.json,
which covers one of the required artifacts for solutions with their own API.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request

from .catalog import build_source
from .config import CARD_RULES_2026, settings
from .db import Store
from .dialog import Dialog
from .max_client import MaxClient, parse_update

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]

state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    source = build_source(
        api_key=settings.proculture_api_key,
        subordinations=settings.proculture_subordinations or None,
        fixture_path=ROOT / settings.catalog_path,
    )
    store = Store(ROOT / settings.db_path)
    state["store"] = store
    state["dialog"] = Dialog(source, store)
    state["source"] = source
    state["max"] = MaxClient(settings.max_bot_token, settings.max_api_base) if settings.has_max_token else None

    log.info(
        "catalogue: %d events, %s, as of %s",
        len(source.all_events()),
        "SYNTHETIC" if source.is_synthetic else "live",
        source.as_of,
    )
    if state["max"] is None:
        log.warning("MAX_BOT_TOKEN not set — the webhook will accept updates but cannot reply")
    yield
    if state.get("max"):
        state["max"].close()
    if state.get("store"):
        state["store"].close()


app = FastAPI(
    title="Pushkin Card leisure assistant",
    description="Helps 14-22 year olds spend their Pushkin Card on events they will actually like.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict:
    """Liveness, plus enough context to tell what this instance is serving."""
    source = state.get("source")
    return {
        "status": "ok",
        "events": len(source.all_events()) if source else 0,
        "data_is_synthetic": source.is_synthetic if source else None,
        "data_as_of": source.as_of if source else None,
        "max_token_configured": settings.has_max_token,
        "db": state["store"].stats() if state.get("store") else None,
        "card_rules": {
            "total": CARD_RULES_2026.total,
            "cinema_cap": CARD_RULES_2026.cinema_cap,
            "as_of": CARD_RULES_2026.as_of,
            "source": CARD_RULES_2026.source,
        },
    }


@app.post("/webhook")
async def webhook(request: Request) -> dict:
    """
    Receive one update from MAX and reply.

    Always returns 200: an error here would make MAX retry, and a retry storm on a
    malformed update is worse than dropping it. Failures go to the log.
    """
    try:
        update = await request.json()
    except Exception:
        log.warning("webhook got a non-JSON body")
        return {"ok": True}

    message = parse_update(update)
    if message is None:
        return {"ok": True}

    try:
        reply = state["dialog"].handle(message.user_id, message.text)
    except Exception:
        log.exception("dialog failed for user %s", message.user_id)
        reply = None

    client = state.get("max")
    if client and reply:
        client.send_message(message.chat_id, reply.text, reply.buttons)
    elif reply:
        log.info("would reply to %s: %s", message.chat_id, reply.text[:80])

    return {"ok": True}
