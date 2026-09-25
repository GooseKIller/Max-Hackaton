"""Stateless UI contract: budgets, safe links, errors and no profile side effects."""
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app import main, planner_api
from app.planner_api import PlanRequest, PlannerService, ticket_url
from test_plans import item


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "settings", replace(main.settings,
        db_path=str(tmp_path / "test.db"), max_bot_token="", proculture_api_key=""))
    monkeypatch.setattr(planner_api, "local_now", lambda: datetime(2026, 9, 25, 12))
    with TestClient(main.app) as http:
        yield http


def test_meta_and_openapi_contract(client):
    response = client.get("/api/planner/meta")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    meta = response.json()
    assert meta["total_limit"] == 5000 and meta["cinema_limit"] == 2000
    assert meta["synthetic"] is True and meta["city"] == "Казань"
    assert "/api/planner/plans" in client.get("/openapi.json").json()["paths"]


def test_real_fixture_plans_are_safe_and_stateless(client):
    before = main.state["store"].stats()
    response = client.post("/api/planner/plans", json={"age": 18, "balance": 3000})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["status"] == "ready" and data["synthetic"] is True
    assert data["cinema_balance"] is None
    assert main.state["store"].stats() == before
    for plan in data["plans"]:
        assert 2 <= len(plan["events"]) <= 3
        assert plan["total"] + plan["remaining"] == 3000
        assert plan["cinema_total"] == 0
        assert sum(e["price"] for e in plan["events"]) == plan["total"]
        assert all(e["ticket_url"] is None for e in plan["events"])


@pytest.mark.parametrize("extra", [
    {"balance": -1}, {"balance": 5001}, {"balance": "3000"}, {"balance": 2.5},
    {"balance": True}, {"age": 13}, {"age": 23}, {"age": None},
    {"cinema_balance": 2001}, {"balance": 100, "cinema_balance": 101},
    {"categories": ["bad"]}, {"categories": ["kino", "kino"]},
    {"availability": "whenever"}, {"user_id": "someone-else"}, {"now": "2026-01-01"},
])
def test_invalid_input_rejected(client, extra):
    response = client.post("/api/planner/plans", json={"age": 18, "balance": 3000, **extra})
    assert response.status_code == 422


def test_zero_balance_and_cinema_without_allowance_are_honest(client):
    data = client.post("/api/planner/plans", json={"age": 18, "balance": 0}).json()
    assert data["plans"] == []
    assert all(e["price"] == 0 for e in data["events"])
    data = client.post("/api/planner/plans", json={"age": 18, "balance": 3000, "categories": ["kino"]}).json()
    assert data["status"] == "no_events"
    assert data["plans"] == data["events"] == []


def test_interests_and_time_are_real_filters(client):
    data = client.post("/api/planner/plans", json={"age": 18, "balance": 3000,
        "categories": ["koncerty"], "availability": "weekends"}).json()
    assert data["events"]
    for event in data["events"] + [e for p in data["plans"] for e in p["events"]]:
        assert event["category"] == "koncerty"
        assert datetime.fromisoformat(event["start"]).weekday() >= 5


class SmallSource:
    is_synthetic = False
    as_of = "2026-09-25"

    def __init__(self, events):
        self.events = events

    def all_events(self):
        return self.events


def test_single_event_fallback_and_variable_price():
    event = replace(item(1).event, is_synthetic=False, max_price=1200,
                    sale_link="https://tickets.example.org/1")
    service = PlannerService(SmallSource([event]))
    result = service.calculate(PlanRequest(age=18, balance=1000), datetime(2026, 9, 25))
    assert result.status == "no_plans"
    assert result.events[0].price_is_minimum
    assert result.events[0].ticket_url == event.sale_link
    event2 = replace(item(2, hour=3).event, is_synthetic=False)
    result = PlannerService(SmallSource([event, event2])).calculate(
        PlanRequest(age=18, balance=1000), datetime(2026, 9, 25))
    assert result.plans[0].estimated is True


def test_expired_horizon_does_not_shift_fake_events_forward():
    service = PlannerService(SmallSource([item(1).event]))
    result = service.calculate(PlanRequest(age=18, balance=1000), datetime(2027, 1, 1))
    assert result.status == "horizon_ended"
    assert result.events == result.plans == []


@pytest.mark.parametrize("url", [
    "javascript:alert(1)", "data:text/html,hi", "http://seller.ru/1", "//seller.ru/1",
    "https://example.invalid/1", "https://user:pass@seller.ru/1", "https://localhost/1",
    "https://[broken/", "https://seller.ru/\nfoo", "",
])
def test_untrusted_links(url):
    assert ticket_url(url, False) is None


def test_synthetic_source_blocks_even_real_looking_links():
    assert ticket_url("https://seller.ru/1", True) is None
    assert ticket_url("https://seller.ru/1", False) == "https://seller.ru/1"


def test_other_category_includes_catalogue_formats_without_a_dedicated_chip():
    service = PlannerService(SmallSource([item(1, category="obuchenie").event]))
    result = service.calculate(PlanRequest(age=18, balance=1000, categories=["prochie"]), datetime(2026, 9, 25))
    assert len(result.events) == 1
    assert result.events[0].category_label == "Обучение"
