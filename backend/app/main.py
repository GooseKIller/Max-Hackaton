"""
The service.

FastAPI serves:
  - /health, so Docker and a judge can see it is alive
  - /webhook, for MAX to post updates to once the bot is deployed
  - /api/planner/*, a stateless budget planner without access to bot profiles
  - /app/, the built React interface (when frontend/dist is present)

For local development there is also a long-polling runner in `runner.py`, which needs
no public HTTPS.

Note for the submission: FastAPI publishes an OpenAPI 3.1 document at /openapi.json,
which covers one of the required artifacts for solutions with their own API.
"""

from __future__ import annotations

import logging
import asyncio
import hmac
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles

from .catalog import build_source
from .config import CARD_RULES_2026, settings
from .db import Store
from .dialog import Dialog
from .delivery import Delivery
from .max_client import MaxClient, parse_update
from .planner_api import PlannerService, router as planner_router

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
    app.state.planner = PlannerService(source)
    state["max"] = MaxClient(settings.max_bot_token, settings.max_api_base,
                             mini_app_bot=settings.mini_app_bot) if settings.has_max_token else None
    state["delivery"] = Delivery(state["dialog"], store, state["max"])

    log.info(
        "catalogue: %d events, %s, as of %s",
        len(source.all_events()),
        "SYNTHETIC" if source.is_synthetic else "live",
        source.as_of,
    )
    if state["max"] is None:
        log.warning("MAX_BOT_TOKEN not set — local planner only; no live bot replies")
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
app.include_router(planner_router)


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
        "webhook_enabled": bool(settings.max_webhook_secret),
        "card_rules": {
            "total": CARD_RULES_2026.total,
            "cinema_cap": CARD_RULES_2026.cinema_cap,
            "as_of": CARD_RULES_2026.as_of,
            "source": CARD_RULES_2026.source,
        },
    }


@app.post("/webhook")
async def webhook(request: Request) -> dict:
    """Secret-checked updates. Malformed updates are ignored; transient failures retry."""
    if not settings.max_webhook_secret:
        raise HTTPException(503, "Webhook disabled")
    secret = request.headers.get("X-Max-Bot-Api-Secret", "")
    if not hmac.compare_digest(secret.encode(), settings.max_webhook_secret.encode()):
        raise HTTPException(403, "Invalid webhook secret")
    if state["delivery"].client is None:
        raise HTTPException(503, "Bot transport not configured")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 65536:
            raise HTTPException(413, "Update too large")
    try:
        update = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        log.warning("webhook got a non-JSON body")
        return {"ok": True}

    message = parse_update(update)
    if message is None:
        return {"ok": True}

    try:
        delivered = await asyncio.to_thread(state["delivery"].handle, message)
    except Exception:
        log.exception("update processing failed")
        raise HTTPException(503, "Retry update")
    if not delivered:
        raise HTTPException(503, "Retry delivery")

    return {"ok": True}


# Same-origin production UI. In development Vite proxies /api to this service.
# API-only and console installations remain usable without Node or a frontend build.
FRONTEND_DIST = ROOT / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/app", StaticFiles(directory=FRONTEND_DIST, html=True), name="planner-ui")
