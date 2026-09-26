"""Serialize conversation updates; persist replies before delivery for safe retries.

Run ONE conversation process per database (webhook OR polling). MAX has no
idempotency key for outgoing messages: a crash after send and before marking sent
can still duplicate a reply, but will not advance the dialog twice.
"""
from dataclasses import asdict
from threading import Lock

from .dialog import Reply


class Delivery:
    def __init__(self, dialog, store, client):
        self.dialog, self.store, self.client = dialog, store, client
        self._lock = Lock()

    def handle(self, message) -> bool:
        # Avoid holding webhook requests past MAX's deadline behind another send.
        if not self._lock.acquire(timeout=1):
            return False
        try:
            if self.client and message.callback_id:
                self.client.answer_callback(message.callback_id)
            key = message.update_key
            receipt = self.store.get_receipt(key) if key else None
            if receipt and receipt["sent"]:
                return True
            if receipt:
                reply = Reply(**receipt["reply"])
            else:
                try:
                    with self.store.atomic():
                        reply = self.dialog.handle(message.user_id, message.text)
                        if key:
                            self.store.save_receipt(key, asdict(reply))
                except Exception:
                    self.dialog.reset(message.user_id)
                    raise
            if self.client and not self.client.send_message(
                message.chat_id, reply.text, reply.buttons, reply.image_url
            ):
                return False
            if key:
                self.store.mark_update_sent(key)
            return True
        finally:
            self._lock.release()
