"""Exercise real service startup against the shipped catalogue, without credentials."""

from dataclasses import replace
from pathlib import Path
import sys
from unittest.mock import Mock
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import main


def test_service_resolves_catalogue_and_opens_database(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "settings", replace(main.settings,
        db_path=str(tmp_path / "test.db"), max_bot_token="", proculture_api_key=""))
    with TestClient(main.app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["events"] > 0
        assert response.json()["data_is_synthetic"] is True
        assert client.get("/openapi.json").status_code == 200


def test_webhook_can_drive_new_budget_step_without_live_max(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "settings", replace(main.settings,
        db_path=str(tmp_path / "test.db"), max_bot_token="", proculture_api_key="",
        max_webhook_secret="test-secret"))
    with TestClient(main.app) as client:
        main.state["delivery"].client = Mock()
        main.state["delivery"].client.send_message.return_value = True
        for text in ("/start", "16", "3000", "без кино"):
            response = client.post("/webhook", headers={"X-Max-Bot-Api-Secret": "test-secret"}, json={
                "update_type": "message_created",
                "message": {"sender": {"user_id": 123},
                            "recipient": {"chat_id": 456}, "body": {"text": text}},
            })
            assert response.status_code == 200
        profile = main.state["store"].load_profile("123")
        assert profile.balance_general == 3000
        assert profile.balance_cinema is None
