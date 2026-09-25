"""Budget and schedule invariants; fixtures are intentionally synthetic."""

import sys
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.filters import affordable
from app.models import Event, Place, Seance, UserProfile
from app.plans import build_plans
from app.taste import Scored

START = datetime(2026, 10, 3, 10)


def item(i, price=500, category="spektakli", hour=0, score=0.5):
    start = START + timedelta(hours=hour)
    slot = Seance(start, start + timedelta(hours=1))
    event = Event(i, f"Тест {i}", 12, "", category, (), (), price, price,
                  "https://example.invalid/ticket", Place("Зал", "teatry", 55.8, 49.1, ""),
                  (slot,), is_synthetic=True)
    return Scored(event, slot, score, {"taste": score}, {})


def profile(total=3000, cinema=1000):
    return UserProfile("u", age=16, balance_general=total, balance_cinema=cinema)


def test_shared_balance_is_not_added_to_cinema_allowance():
    assert build_plans([item(1, 2000), item(2, 1500, "kino", 3)], profile(3000, 2000)) == []


def test_cinema_aggregate_obeys_remaining_sub_limit():
    assert build_plans([item(1, 600, "kino"), item(2, 600, "kino", 3)], profile()) == []


def test_all_money_can_go_to_non_cinema():
    plans = build_plans([item(1, 2500), item(2, 2500, hour=3)], profile(5000, 2000))
    assert plans[0].total == 5000
    assert plans[0].remaining == 0


@pytest.mark.parametrize("cinema", [None, 0])
def test_unknown_or_exhausted_cinema_is_excluded(cinema):
    plans = build_plans([item(1, 400, "kino"), item(2, hour=3), item(3, hour=6)], profile(cinema=cinema))
    assert plans and all(not s.event.is_cinema for p in plans for s in p.items)


@pytest.mark.parametrize("total", [None, 0, 400])
def test_no_funded_plan_without_sufficient_reported_balance(total):
    assert build_plans([item(1), item(2, hour=3)], profile(total)) == []


def test_single_film_cannot_exceed_total_or_annual_cinema_limit():
    assert not affordable(item(1, 500, "kino").event, profile(100, 1000))
    assert not affordable(item(1, 2100, "kino").event, profile(5000, 5000))


@pytest.mark.parametrize("hour", [0, 1])
def test_overlaps_and_insufficient_transfer_time_are_rejected(hour):
    assert build_plans([item(1), item(2, hour=hour)], profile()) == []


def test_missing_duration_cannot_form_a_scheduled_plan():
    first = item(1)
    first.seance = Seance(START, START)
    assert build_plans([first, item(2, hour=3)], profile()) == []


def test_duplicate_event_ids_cannot_fill_a_plan():
    assert build_plans([item(1), item(1, hour=3)], profile()) == []


def test_same_production_at_same_venue_is_not_repeated_under_different_ids():
    first, second = item(1), item(2, hour=3)
    second.event = replace(second.event, name=first.event.name)
    assert build_plans([first, second], profile()) == []


def test_three_modes_have_distinct_sets_and_correct_arithmetic():
    candidates = [item(1, 800, score=.9), item(2, 500, "vystavki", 3, .8),
                  item(3, 900, "koncerty", 6, .7), item(4, 1700, hour=9)]
    plans = build_plans(candidates, profile())
    assert len(plans) == 3
    assert len({frozenset(s.event.id for s in p.items) for p in plans}) == len(plans)
    for plan in plans:
        assert 2 <= len(plan.items) <= 3
        assert plan.total == sum(s.event.price for s in plan.items) <= 3000
        assert plan.remaining == 3000 - plan.total
        assert plan.cinema_total <= 1000


def test_search_is_bounded_and_deterministic():
    rows = [item(i, hour=i*3) for i in range(50)]
    plans = build_plans(rows, profile())
    assert plans == build_plans(rows, profile())
    assert all(s.event.id < 30 for p in plans for s in p.items)


def test_current_year_planning_horizon():
    second = item(2)
    future = datetime(2027, 1, 2, 10)
    second.seance = Seance(future, future + timedelta(hours=1))
    assert build_plans([item(1), second], profile()) == []
