"""
Tests for when the polling service is allowed to run.

`docker compose up` now starts polling by default, which means the guard around it
is the difference between a bot that works and a bot that eats half its own
messages. Both cases are load-bearing.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from runner import blocking_reason  # noqa: E402


class FakeClient:
    def __init__(self, subscriptions=None):
        self._subscriptions = subscriptions or []
        self.asked = False

    def list_subscriptions(self):
        self.asked = True
        return self._subscriptions


def test_polls_when_a_token_exists_and_no_webhook_is_registered():
    client = FakeClient([])
    assert blocking_reason(client, has_token=True) is None
    assert client.asked


def test_refuses_without_a_token():
    client = FakeClient([])
    reason = blocking_reason(client, has_token=False)
    assert reason and "MAX_BOT_TOKEN" in reason
    assert not client.asked, "asked MAX about subscriptions without a token"


def test_refuses_when_a_webhook_is_already_registered():
    """
    MAX gives each update to one consumer. A poller beside a webhook does not
    duplicate traffic, it steals a random share — the bot then answers roughly
    every other message, intermittently, which is miserable to diagnose.
    """
    client = FakeClient([{"url": "https://example.org/webhook"}])
    reason = blocking_reason(client, has_token=True)
    assert reason and "webhook" in reason
    assert "example.org" in reason, "the reason should name the webhook it found"


def test_a_subscription_without_a_url_still_blocks():
    client = FakeClient([{}])
    assert blocking_reason(client, has_token=True) is not None
