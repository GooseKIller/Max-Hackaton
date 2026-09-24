"""
MAX Bot API client.

Deliberately thin: we call the REST API directly rather than depending on an SDK we
have not verified. Per the brief, MAX documentation changes and third-party examples
should not be trusted — so everything here is written against dev.max.ru/docs-api and
should be re-checked before submission.

Two ways to receive updates:
  - long polling (GET /updates) — no public HTTPS needed, good for development
  - webhooks (POST /subscriptions) — needed for the deployed bot

Both are here. Long polling is the default because it works from a laptop.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class IncomingMessage:
    """One user message, normalised out of whatever shape MAX sends."""

    user_id: str
    chat_id: int
    text: str


class MaxClient:
    def __init__(self, token: str, base_url: str, timeout: float = 65.0):
        if not token:
            raise ValueError("MAX_BOT_TOKEN is empty")
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": token},
            timeout=timeout,
        )
        self._marker: int | None = None

    def close(self) -> None:
        self._client.close()

    # -- sending -------------------------------------------------------------

    def send_message(self, chat_id: int, text: str, buttons: list[str] | None = None) -> None:
        """
        Send a message, optionally with suggested replies.

        The keyboard payload shape is the part most likely to be wrong until we test
        against a real bot token — it is isolated here for exactly that reason.
        """
        payload: dict[str, Any] = {"text": text}
        if buttons:
            payload["attachments"] = [
                {
                    "type": "inline_keyboard",
                    "payload": {
                        "buttons": [
                            [{"type": "callback", "text": b, "payload": b}]
                            for b in buttons
                        ]
                    },
                }
            ]
        try:
            r = self._client.post("/messages", params={"chat_id": chat_id}, json=payload)
            r.raise_for_status()
        except httpx.HTTPError as exc:
            # A failed send must not kill the loop — the next update still deserves
            # a chance. Errors are visible in the logs.
            log.error("send_message failed for chat %s: %s", chat_id, exc)

    # -- receiving -----------------------------------------------------------

    def get_updates(self, timeout: int = 60) -> list[IncomingMessage]:
        """Long-poll for updates. Blocks up to `timeout` seconds."""
        params: dict[str, Any] = {"timeout": timeout}
        if self._marker is not None:
            params["marker"] = self._marker
        try:
            r = self._client.get("/updates", params=params)
            r.raise_for_status()
            body = r.json()
        except httpx.HTTPError as exc:
            log.warning("get_updates failed: %s", exc)
            return []
        except ValueError:
            log.warning("get_updates returned non-JSON")
            return []

        self._marker = body.get("marker", self._marker)
        return [m for m in (parse_update(u) for u in body.get("updates", [])) if m]

    def subscribe_webhook(self, url: str) -> None:
        """Register a webhook for the deployed bot."""
        r = self._client.post("/subscriptions", json={"url": url})
        r.raise_for_status()


def parse_update(update: dict) -> IncomingMessage | None:
    """
    Pull a usable message out of one update.

    Handles both a plain message and a button press (callback), because to the
    dialog those are the same thing: a piece of text from a user.
    """
    kind = update.get("update_type") or update.get("type")

    if kind in ("message_created", "message"):
        msg = update.get("message") or {}
        body = msg.get("body") or {}
        sender = (msg.get("sender") or {}).get("user_id")
        chat_id = (msg.get("recipient") or {}).get("chat_id")
        text = body.get("text") or ""
        if sender is None or chat_id is None:
            return None
        return IncomingMessage(user_id=str(sender), chat_id=int(chat_id), text=text)

    if kind in ("message_callback", "callback"):
        cb = update.get("callback") or {}
        msg = update.get("message") or {}
        sender = (cb.get("user") or {}).get("user_id")
        chat_id = (msg.get("recipient") or {}).get("chat_id")
        text = cb.get("payload") or ""
        if sender is None or chat_id is None:
            return None
        return IncomingMessage(user_id=str(sender), chat_id=int(chat_id), text=text)

    return None
