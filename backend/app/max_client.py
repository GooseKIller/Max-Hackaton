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
    # Present for a button press. MAX expects the press to be acknowledged, or the
    # button keeps showing a spinner in the client.
    callback_id: str | None = None


class MaxClient:
    def __init__(self, token: str, base_url: str, timeout: float = 65.0):
        if not token:
            raise ValueError("MAX_BOT_TOKEN is empty")
        from .config import ssl_context

        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": token},
            timeout=timeout,
            verify=ssl_context(),
        )
        self._marker: int | None = None

    def close(self) -> None:
        self._client.close()

    # -- sending -------------------------------------------------------------

    def send_message(
        self,
        chat_id: int,
        text: str,
        buttons: list[str] | None = None,
        image_url: str | None = None,
    ) -> None:
        """
        Send a message, optionally with a picture and suggested replies.

        Keyboard shape verified against a live bot on 26 September 2026.

        MAX fetches `image_url` from its own servers, which fails for hosts it
        cannot reach and occasionally fails for hosts it can — we saw the same
        culture.ru URL rejected once and accepted a moment later. So a picture is
        best-effort: if the message with the attachment is refused, we resend
        without it rather than dropping the reply. A card with no photo is a
        disappointment; a silent bot is a broken one.
        """
        keyboard = None
        if buttons:
            keyboard = {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": [
                        [{"type": "callback", "text": b, "payload": b}] for b in buttons
                    ]
                },
            }

        def attempt(with_image: bool) -> bool:
            payload: dict[str, Any] = {"text": text}
            attachments = []
            if with_image and image_url:
                attachments.append({"type": "image", "payload": {"url": image_url}})
            if keyboard:
                attachments.append(keyboard)
            if attachments:
                payload["attachments"] = attachments
            try:
                r = self._client.post(
                    "/messages", params={"chat_id": chat_id}, json=payload
                )
            except httpx.HTTPError as exc:
                log.error("send_message request failed for chat %s: %s", chat_id, exc)
                return False
            if r.status_code < 400:
                return True
            log.warning(
                "send_message HTTP %s (image=%s): %s",
                r.status_code, bool(with_image and image_url), r.text[:160],
            )
            return False

        if attempt(with_image=True):
            return
        if image_url and attempt(with_image=False):
            log.info("resent without the picture for chat %s", chat_id)

    # -- receiving -----------------------------------------------------------

    def answer_callback(self, callback_id: str) -> None:
        """
        Acknowledge a button press.

        Without this the client leaves the button spinning even though we replied.
        Failures are logged and swallowed: a missing acknowledgement is cosmetic,
        and must not stop us answering the user.

        The body is NOT optional. The documentation shows `{}` as a valid minimal
        request; a live bot answers
        `{"code":"proto.payload","message":"Invalid request. \`message\` or
        \`notification\` required"}`. An empty `notification` satisfies it without
        showing the user a toast.
        """
        try:
            r = self._client.post(
                "/answers",
                params={"callback_id": callback_id},
                json={"notification": ""},
            )
            if r.status_code >= 400:
                # Log what MAX actually objected to. A bare status code sent us
                # chasing the wrong thing once already.
                log.warning(
                    "answer_callback HTTP %s: %s (id len=%d, starts %r)",
                    r.status_code, r.text[:200], len(callback_id), callback_id[:12],
                )
        except httpx.HTTPError as exc:
            log.warning("answer_callback request failed: %s", exc)

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
        log.debug("raw callback update: %s", update)
        msg = update.get("message") or {}
        sender = (cb.get("user") or {}).get("user_id")
        chat_id = (msg.get("recipient") or {}).get("chat_id")
        text = cb.get("payload") or ""
        if sender is None or chat_id is None:
            return None
        return IncomingMessage(
            user_id=str(sender),
            chat_id=int(chat_id),
            text=text,
            callback_id=cb.get("callback_id"),
        )

    if kind in ("bot_started", "bot_add"):
        # Sent when someone opens the bot for the first time. Without this the very
        # first interaction produces nothing at all and the bot looks broken before
        # it has said a word. Treat it as "/start": it is the same intent.
        chat_id = update.get("chat_id") or (update.get("chat") or {}).get("chat_id")
        sender = (update.get("user") or {}).get("user_id")
        if sender is None or chat_id is None:
            return None
        return IncomingMessage(user_id=str(sender), chat_id=int(chat_id), text="/start")

    return None
