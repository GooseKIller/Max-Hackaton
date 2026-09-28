"""Process shutdown and delivery retries, with no external transports."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import signal
import sqlite3
import sys
from threading import Event
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import runner
from app import reminder_worker
from app.db import Store
from app.delivery import Delivery
from app.dialog import Reply
from app.max_client import IncomingMessage
from app.models import UserProfile
from app.process_control import shutdown_event
from app.reminders import MSK, run_once


class TestStop(Event):
    __test__ = False

    def __init__(self, stop_on_wait=False):
        super().__init__()
        self.waits = []
        self.stop_on_wait = stop_on_wait

    def wait(self, timeout=None):
        self.waits.append(timeout)
        if self.stop_on_wait:
            self.set()
        return self.is_set()


def test_shutdown_signal_sets_event_and_restores_handlers():
    previous = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
    with shutdown_event() as stop:
        assert not stop.is_set()
        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        assert stop.is_set()
    assert {s: signal.getsignal(s) for s in previous} == previous


def test_poll_retries_same_receipt_after_temporary_failures(tmp_path):
    store = Store(tmp_path / "polling.db")
    stop = TestStop()
    handled = []

    class Dialog:
        def handle(self, uid, text):
            handled.append(text)
            return Reply(text)

        def reset(self, uid):
            pass

    class Client:
        reads = 0
        sent = []

        def get_updates(self):
            self.reads += 1
            assert self.reads == 1, "Must finish this batch before polling again"
            return [IncomingMessage("1", 1, "first", update_key="first"),
                    IncomingMessage("1", 1, "second", update_key="second")]

        def send_message(self, chat_id, text, buttons, image_url):
            self.sent.append(text)
            if text == "second":
                stop.set()
            return len(self.sent) > 2

    client = Client()
    try:
        runner.poll_updates(client, Delivery(Dialog(), store, client), stop)
        assert handled == ["first", "second"]
        assert client.sent == ["first"] * 3 + ["second"]
        assert stop.waits == [1, 2]
        assert store.get_receipt("first")["sent"]
        assert store.get_receipt("second")["sent"]
    finally:
        store.close()


@pytest.mark.parametrize("dialog_fails", [False, True])
def test_failed_chat_does_not_block_another_user(tmp_path, dialog_fails):
    path = tmp_path / "failed-chat.db"
    store = Store(path)
    stop = TestStop()
    handled, sent = [], []
    blocked = IncomingMessage("blocked", 1, "first", update_key="first")
    other = IncomingMessage("other", 2, "second", update_key="second")

    class Dialog:
        def handle(self, uid, text):
            handled.append(uid)
            if dialog_fails and uid == "blocked":
                raise ValueError("invalid conversation")
            return Reply(text)

        def reset(self, uid):
            pass

    class Client:
        def get_updates(self):
            return [blocked, other]

        def send_message(self, chat_id, text, buttons, image_url):
            sent.append(chat_id)
            if chat_id == 2:
                stop.set()
                return True
            return False

    try:
        client = Client()
        runner.poll_updates(client, Delivery(Dialog(), store, client), stop)
        assert sent[-1] == 2
        assert handled.count("blocked") == (3 if dialog_fails else 1)
        assert stop.waits == [1, 2]
        assert store.get_receipt("second")["sent"]
        if dialog_fails:
            assert store.get_receipt("first") is None
        else:
            assert sent == [1, 1, 1, 2]
            assert not store.get_receipt("first")["sent"]
    finally:
        store.close()

    if not dialog_fails:
        # If MAX redelivers later, the saved reply survives a process restart.
        store = Store(path)
        recovered = SimpleNamespace(send_message=lambda *args: True)
        try:
            assert Delivery(Dialog(), store, recovered).handle(blocked)
            assert handled.count("blocked") == 1
            assert store.get_receipt("first")["sent"]
        finally:
            store.close()


def test_poll_stops_during_failed_delivery_backoff():
    stop = TestStop(stop_on_wait=True)
    message = IncomingMessage("1", 1, "hello")
    delivery = SimpleNamespace(handle=lambda _: False)
    runner.poll_updates(SimpleNamespace(get_updates=lambda: [message]), delivery, stop)
    assert stop.waits == [1]


def test_empty_poll_waits_instead_of_spinning():
    stop = TestStop(stop_on_wait=True)
    runner.poll_updates(SimpleNamespace(get_updates=lambda: []), None, stop)
    assert stop.waits == [1]


@pytest.mark.parametrize("fail_client", [False, True])
def test_polling_main_closes_resources(tmp_path, monkeypatch, fail_client):
    stores, clients = [], []
    previous = signal.getsignal(signal.SIGTERM)

    def make_store(path):
        stores.append(Store(path))
        return stores[-1]

    class Client:
        closed = False

        def __init__(self, *args, **kwargs):
            if fail_client:
                raise RuntimeError("fake initialization failure")
            clients.append(self)

        def list_subscriptions(self):
            # No webhook registered, so polling is allowed to start.
            return []

        def get_updates(self):
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
            return []

        def close(self):
            self.closed = True

    monkeypatch.setattr(runner, "settings", replace(runner.settings,
        max_bot_token="fake", db_path=str(tmp_path / "main.db"), proculture_api_key=""))
    monkeypatch.setattr(runner, "build_source", lambda **kw: SimpleNamespace(
        all_events=lambda: [], is_synthetic=True))
    monkeypatch.setattr(runner, "Store", make_store)
    monkeypatch.setattr(runner, "MaxClient", Client)
    if fail_client:
        with pytest.raises(RuntimeError, match="fake initialization failure"):
            runner.main()
    else:
        runner.main()
        assert clients[0].closed
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        stores[0]._conn.execute("SELECT 1")
    assert signal.getsignal(signal.SIGTERM) == previous


def test_worker_hourly_wait_is_interruptible_and_closes_resources(tmp_path, monkeypatch):
    stop = TestStop(stop_on_wait=True)
    stores, senders, passes = [], [], []

    @contextmanager
    def stopping():
        yield stop

    def make_store(path):
        stores.append(Store(path))
        return stores[-1]

    class Sender:
        closed = False

        def __init__(self, *args):
            senders.append(self)

        def close(self):
            self.closed = True

    monkeypatch.setattr(reminder_worker, "settings", replace(reminder_worker.settings,
        max_bot_token="fake", db_path=str(tmp_path / "worker.db")))
    monkeypatch.setattr(reminder_worker, "shutdown_event", stopping)
    monkeypatch.setattr(reminder_worker, "Store", make_store)
    monkeypatch.setattr(reminder_worker, "MaxSender", Sender)
    monkeypatch.setattr(reminder_worker, "_pass", lambda *args: passes.append(args))
    monkeypatch.setattr(sys, "argv", ["worker", "--loop"])
    reminder_worker.main()
    assert len(passes) == 1
    assert stop.waits == [reminder_worker.LOOP_EVERY_SECONDS]
    assert senders[0].closed
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        stores[0]._conn.execute("SELECT 1")


def test_reminder_stop_leaves_remaining_users_unsent(tmp_path):
    store = Store(tmp_path / "batch.db")
    stop = Event()
    for uid in ("1", "2"):
        store.save_profile(UserProfile(user_id=uid, age=18, balance_general=3000))
        store.set_reminder_opt_in(uid, True)
    sent = []

    def send(reminder):
        sent.append(reminder.user_id)
        stop.set()
        return True

    try:
        result = run_once(store, send, datetime(2026, 12, 1, 12, tzinfo=MSK), stop.is_set)
        assert result == {"sent": 1, "failed": 0}
        assert len(sent) == 1
        assert store.reminder_status(sent[0], 2026, "d30") == "sent"
        other = ({"1", "2"} - set(sent)).pop()
        assert store.reminder_status(other, 2026, "d30") is None
    finally:
        store.close()


def test_reminder_stop_after_claim_does_not_mark_it_sent(tmp_path, monkeypatch):
    store = Store(tmp_path / "claimed.db")
    store.save_profile(UserProfile(user_id="1", age=18, balance_general=3000))
    store.set_reminder_opt_in("1", True)
    stop, sent = Event(), []
    claim = store.claim_reminder

    def claim_then_stop(*args, **kwargs):
        result = claim(*args, **kwargs)
        stop.set()
        return result

    monkeypatch.setattr(store, "claim_reminder", claim_then_stop)
    try:
        result = run_once(store, lambda r: sent.append(r),
                          datetime(2026, 12, 1, 12, tzinfo=MSK), stop.is_set)
        assert result == {"sent": 0, "failed": 0}
        assert not sent
        assert store.reminder_status("1", 2026, "d30") == "sending"
    finally:
        store.close()
