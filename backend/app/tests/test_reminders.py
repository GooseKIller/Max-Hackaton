"""Reminder scheduling: day maths, band selection, de-duplication, copy and one pass."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db import Store
from app.models import UserProfile
from app import reminders
from app.reminders import (
    MSK,
    Reminder,
    days_left,
    render,
    rule_for,
    run_once,
)


def _store(tmp_path) -> Store:
    return Store(tmp_path / "t.db")


# -- day maths --------------------------------------------------------------


def test_days_left_excludes_expiry_year_end():
    # Expiry is 2026-12-31 (config.BALANCE_EXPIRES).
    assert days_left(datetime(2026, 12, 31, 12, 0, tzinfo=MSK)) == 0
    assert days_left(datetime(2026, 12, 28, 12, 0, tzinfo=MSK)) == 3
    assert days_left(datetime(2026, 12, 1, 12, 0, tzinfo=MSK)) == 30


def test_days_left_uses_moscow_date():
    # 2026-12-30 23:30 UTC is already 2026-12-31 02:30 in Moscow -> 0 days, not 1.
    utc_late = datetime(2026, 12, 30, 23, 30, tzinfo=timezone.utc)
    assert days_left(utc_late) == 0


# -- band selection ---------------------------------------------------------


def test_rule_bands_do_not_overlap_and_cover_the_windows():
    assert rule_for(30) == "d30"
    assert rule_for(15) == "d30"
    assert rule_for(14) == "d14"
    assert rule_for(4) == "d14"
    assert rule_for(3) == "d3"
    assert rule_for(0) == "d3"
    # Outside any band: too early, or expired.
    assert rule_for(31) is None
    assert rule_for(60) is None


# -- de-duplication ---------------------------------------------------------


def test_claim_is_once_then_reclaims_only_when_stale(tmp_path):
    store = _store(tmp_path)
    far_past = "2000-01-01T00:00:00+03:00"
    future = "2100-01-01T00:00:00+03:00"

    # First claim wins.
    assert store.claim_reminder("u1", 2026, "d30", far_past) is True
    # Second, while fresh (nothing older than `future` is... everything is), must NOT
    # re-claim a slot that is not stale: pass a stale-before far in the past.
    assert store.claim_reminder("u1", 2026, "d30", far_past) is False
    # A stale 'sending' row (claimed before `future`) can be reclaimed.
    assert store.claim_reminder("u1", 2026, "d30", future) is True
    # Once marked sent, it never re-claims.
    store.mark_reminder_sent("u1", 2026, "d30")
    assert store.claim_reminder("u1", 2026, "d30", future) is False
    assert store.reminder_status("u1", 2026, "d30") == "sent"


# -- copy / tone ------------------------------------------------------------


def test_render_states_fact_without_pressure():
    r = render("u1", "d14", 14, 3000, "2026-09-20T10:00:00+03:00")
    assert "!" not in r.text
    for banned in ("успей", "не упусти", "срочно", "сгорят!"):
        assert banned.lower() not in r.text.lower()
    assert "14 дней" in r.text
    assert "3000" in r.text
    assert "20.09" in r.text  # the date the balance was reported


def test_render_plural_days_is_correct():
    assert "21 день" in render("u", "d30", 21, None, None).text
    assert "22 дня" in render("u", "d30", 22, None, None).text
    assert "25 дней" in render("u", "d30", 25, None, None).text


def test_render_without_balance_says_nothing_it_cannot_verify():
    r = render("u1", "d3", 3, None, None)
    assert "₽" not in r.text  # no invented number
    assert "3 дня" in r.text


# -- one pass, end to end (no network) --------------------------------------


def test_run_once_sends_to_opted_in_and_is_idempotent(tmp_path):
    store = _store(tmp_path)
    store.save_profile(UserProfile(user_id="opted", age=17, balance_general=3000,
                                   balance_reported_at="2026-12-01T10:00:00+03:00"))
    store.save_profile(UserProfile(user_id="silent", age=17, balance_general=2000))
    store.set_reminder_opt_in("opted", True)
    # 'silent' never opted in.

    sent: list[Reminder] = []

    def fake_send(r: Reminder) -> bool:
        sent.append(r)
        return True

    now = datetime(2026, 12, 1, 12, 0, tzinfo=MSK)  # 30 days left -> d30 band
    first = run_once(store, fake_send, now)
    assert first == {"sent": 1, "failed": 0}
    assert [r.user_id for r in sent] == ["opted"]

    # A second pass the same day must not send again.
    second = run_once(store, fake_send, now)
    assert second == {"sent": 0, "failed": 0}
    assert len(sent) == 1


def test_run_once_failed_send_is_retried_not_marked(tmp_path):
    store = _store(tmp_path)
    store.save_profile(UserProfile(user_id="u", age=17, balance_general=3000))
    store.set_reminder_opt_in("u", True)
    now = datetime(2026, 12, 1, 12, 0, tzinfo=MSK)

    result = run_once(store, lambda r: False, now)  # delivery fails
    assert result == {"sent": 0, "failed": 1}
    assert store.reminder_status("u", 2026, "d30") == "sending"  # not 'sent'

    # A later pass, after the stale window, retries and this time succeeds.
    later = now + timedelta(minutes=11)
    ok = run_once(store, lambda r: True, later)
    assert ok == {"sent": 1, "failed": 0}
    assert store.reminder_status("u", 2026, "d30") == "sent"
