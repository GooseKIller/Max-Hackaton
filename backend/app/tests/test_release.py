"""Deployment boundaries and reminder consent. All transports are fake."""
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
import sys

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main, reminder_worker
from app.db import Store
from app.delivery import Delivery
from app.dialog import Dialog, Reply, Step
from app.max_client import MaxClient, parse_update
from app.models import UserProfile
from app.reminders import MSK, due, run_once
from test_dialog_budget import Source, NOW


def update(text="/start", mid="1"):
    return {"update_type": "message_created", "message": {
        "sender": {"user_id": 123}, "recipient": {"chat_id": 456},
        "body": {"text": text, "mid": mid}}}


class Sender:
    def __init__(self, success=True):
        self.sent, self.answers, self.success = [], [], success

    def send_message(self, *args):
        self.sent.append(args)
        return self.success

    def answer_callback(self, callback_id):
        self.answers.append(callback_id)

    def close(self): pass


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "settings", replace(main.settings,
        max_bot_token="", proculture_api_key="", max_webhook_secret="test-secret",
        db_path=str(tmp_path / "service.db")))
    with TestClient(main.app) as client:
        main.state["delivery"].client = Sender()
        client.headers["X-Max-Bot-Api-Secret"] = "test-secret"
        yield client


def test_webhook_secret_and_public_health(service):
    assert service.post("/webhook", json=update(), headers={"X-Max-Bot-Api-Secret":"wrong"}).status_code == 403
    assert main.state["store"].load_profile("123") is None
    assert "db" not in service.get("/health").json()


def test_webhook_disabled_by_default(service, monkeypatch):
    monkeypatch.setattr(main, "settings", replace(main.settings, max_webhook_secret=""))
    assert service.post("/webhook", json=update()).status_code == 503


def test_webhook_never_discards_update_without_bot_transport(service):
    main.state["delivery"].client = None
    assert service.post("/webhook", json=update()).status_code == 503
    assert main.state["store"].load_profile("123") is None


@pytest.mark.parametrize("payload", [None, [], "text", 42, {"message": []},
    {"update_type":"message_callback","callback":{"user": []}},
    {"update_type":"message_created","message":{"sender":{"user_id":1},
      "recipient":{"chat_id":"invalid"},"body":{"text":"hi"}}}])
def test_bad_updates_do_not_crash(service, payload):
    assert parse_update(payload) is None
    assert service.post("/webhook", json=payload).status_code == 200


def test_webhook_size_limit(service):
    assert service.post("/webhook", content=b"x" * 65537).status_code == 413


def test_duplicate_webhook_does_not_advance_dialog(service):
    for _ in range(2):
        assert service.post("/webhook", json=update()).status_code == 200
    for _ in range(2):
        assert service.post("/webhook", json=update("18", "2")).status_code == 200
    p = main.state["store"].load_profile("123")
    assert p.age == 18 and p.balance_general is None


def test_webhook_callback_ack_and_send_failure_retry(service):
    sender = Sender(False)
    main.state["delivery"].client = sender
    cb = {"update_type":"message_callback", "callback":{
        "user":{"user_id":123}, "callback_id":"cb-1", "payload":"/start"},
        "message":{"recipient":{"chat_id":456}}}
    assert service.post("/webhook", json=cb).status_code == 503
    sender.success = True
    assert service.post("/webhook", json=cb).status_code == 200
    assert service.post("/webhook", json=cb).status_code == 200
    assert sender.answers == ["cb-1"] * 3
    assert len(sender.sent) == 2
    assert sender.sent[0] == sender.sent[1]


def test_receipt_survives_restart_and_rolls_back_errors(tmp_path):
    path = tmp_path / "state.db"
    store = Store(path)
    sender = Sender()
    d = Dialog(Source(), store)
    message = parse_update(update())
    Delivery(d, store, sender).handle(message)
    store.close()
    store = Store(path)
    assert Delivery(Dialog(Source(), store), store, sender).handle(message)
    assert len(sender.sent) == 1

    class BrokenDialog:
        def handle(self, uid, text):
            store.save_profile(UserProfile(user_id="should-rollback", age=18))
            raise RuntimeError("fake failure")
        def reset(self, uid): pass
    with pytest.raises(RuntimeError):
        Delivery(BrokenDialog(), store, sender).handle(parse_update(update("x", "2")))
    assert store.load_profile("should-rollback") is None
    store.close()


def test_keyboard_app_is_opt_in_and_send_reports_failure():
    client = MaxClient("fake", "https://example.invalid", mini_app_bot="test_bot")
    client._client.close()
    requests = []
    def transport(request):
        requests.append(request)
        return httpx.Response(400, json={"error":"fake"})
    client._client = httpx.Client(base_url="https://example.invalid", transport=httpx.MockTransport(transport))
    assert client.keyboard_rows(["Открыть планы"])[0][0] == {
        "type":"open_app", "text":"Открыть планы", "web_app":"test_bot"}
    assert client.send_message(1, "hello", ["Открыть планы"], "https://example.invalid/pic") is False
    assert len(requests) == 2
    client._mini_app_bot = ""
    assert client.keyboard_rows(["Открыть планы"]) == []
    client.close()


def enrolled(store, uid="123"):
    store.save_profile(UserProfile(user_id=uid, age=18, balance_general=3000,
        balance_reported_at="2026-12-01T12:00:00+03:00"))
    store.set_reminder_opt_in(uid, True)


def test_reminders_expired_quiet_hours_zero_balance_and_retry(tmp_path):
    store = Store(tmp_path / "reminders.db")
    enrolled(store)
    now = datetime(2026, 12, 1, 12, tzinfo=MSK)
    assert len(due(store, now)) == 1
    assert due(store, datetime(2027, 1, 1, 12, tzinfo=MSK)) == []
    assert due(store, now.replace(hour=3)) == []
    assert run_once(store, lambda _: False, now)["failed"] == 1
    assert run_once(store, lambda _: True, now + timedelta(minutes=5))["sent"] == 0
    assert run_once(store, lambda _: True, now + timedelta(minutes=11))["sent"] == 1
    enrolled(store, "zero")
    store.save_profile(UserProfile(user_id="zero", age=18, balance_general=0))
    assert due(store, now) == []
    store.close()


def test_consent_and_reminder_actions_are_reachable(tmp_path):
    store = Store(tmp_path / "dialog.db")
    dialog = Dialog(Source(), store)
    for text in ["/start", "18", "3000"]:
        dialog.handle("123", text, NOW)
    assert not store.is_opted_in("123")
    assert "Включить напоминания" in dialog.handle("123", "напоминания", NOW).buttons
    dialog.handle("123", "Включить напоминания", NOW)
    assert store.is_opted_in("123")
    assert "Итого" in dialog.handle("123", "Показать наборы", NOW).text
    dialog.handle("123", "Обновить остаток", NOW)
    assert dialog._session("123").step is Step.EDIT_BALANCE
    dialog.handle("123", "Отключить напоминания", NOW)
    assert not store.is_opted_in("123")
    store.close()


def test_dry_run_leaves_delivery_state_untouched(tmp_path, monkeypatch):
    path = tmp_path / "dry.db"
    store = Store(path)
    enrolled(store)
    store.close()
    monkeypatch.setattr(reminder_worker, "settings", replace(main.settings, db_path=str(path)))
    monkeypatch.setattr(sys, "argv", ["worker", "--once", "--dry-run"])
    now = datetime(2026, 12, 1, 12, tzinfo=MSK)
    monkeypatch.setattr(reminder_worker, "due", lambda s: due(s, now))
    reminder_worker.main()
    store = Store(path)
    assert store.reminder_status("123", 2026, "d30") is None
    store.close()


def test_docker_ships_photos():
    root = Path(__file__).resolve().parents[3]
    assert "COPY data/venue_photos.json" in (root / "backend/Dockerfile").read_text()


def test_feed_survives_restart_without_losing_current_card(tmp_path):
    path = tmp_path / "restart.db"
    store = Store(path)
    dialog = Dialog(Source(), store)
    for text in ["/start", "18", "3000", "не моё"]:
        dialog.handle("123", text, NOW)
    old = dialog._session("123")
    shown = old.last_shown[0].event.id
    store.close()
    store = Store(path)
    restored = Dialog(Source(), store)
    assert restored._session("123").last_shown[0].event.id == shown
    assert restored._session("123").swiped == old.swiped
    restored.handle("123", "пойду", NOW)
    liked = store._conn.execute("SELECT event_id FROM interactions WHERE signal='like'").fetchall()
    assert [r["event_id"] for r in liked] == [shown]
    store.close()


def test_unknown_balance_can_opt_in_and_duplicate_uses_message_id(tmp_path):
    store = Store(tmp_path / "unknown.db")
    dialog = Dialog(Source(), store)
    for text in ("/start", "18", "не знаю", "Включить напоминания"):
        dialog.handle("123", text, NOW)
    assert store.is_opted_in("123")
    assert len(due(store, datetime(2026, 12, 1, 12, tzinfo=MSK))) == 1
    assert parse_update({**update(), "timestamp":1}).update_key == parse_update({**update(), "timestamp":2}).update_key
    store.close()
