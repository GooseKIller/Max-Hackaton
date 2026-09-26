"""User-visible regressions: exact balances, unknown values, restart and plans."""

import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db import Store
from app.dialog import Dialog, Step
from test_plans import item

NOW = datetime(2026, 10, 1, 12)


class Source:
    is_synthetic = True
    as_of = "2026-10-01"

    def all_events(self):
        return [item(1).event, item(2, hour=3).event,
                item(3, 700, "vystavki", 6).event, item(4, 600, "kino", 9).event]


def send(d, text, now=NOW):
    return d.handle("u", text, now)


def start(d):
    send(d, "/start")
    send(d, "16")


def finish(d, swipes=3):
    """Get past onboarding into a warmed-up feed.

    The flow used to ask about time and mood and then run a five-card quiz. It now
    drops straight into the swipe feed, so "finishing" onboarding means swiping a
    few cards — which is also what unlocks the plan button.
    """
    for _ in range(swipes):
        if d._session("u").step is Step.SWIPE:
            send(d, "не моё")


@pytest.mark.parametrize("bad", ["-500", "12.5", "1000–2500", "500 и 200", "5000 рублей 2000 кино", "99999999999"])
def test_invalid_balance_is_not_silently_reinterpreted(bad):
    d = Dialog(Source())
    start(d)
    send(d, bad)
    assert d._session("u").step is Step.ASK_BALANCE
    assert d._session("u").profile.balance_general is None


def test_unknown_balance_is_browsing_without_fabricated_money():
    d = Dialog(Source())
    start(d)
    send(d, "не знаю")
    finish(d)
    assert d._session("u").profile.balance_general is None
    assert "точный остаток" in send(d, "/plan").text
    assert "не указан" in send(d, "/balance").text


def test_cinema_is_asked_not_inferred_from_total():
    d = Dialog(Source())
    start(d)
    send(d, "1 500 ₽")
    # Onboarding no longer asks about cinema: it starts without it rather than
    # spending a step before the user has seen anything at all.
    assert d._session("u").step is Step.SWIPE
    assert d._session("u").profile.balance_cinema is None
    # But it must be asked, never inferred from the total, when it matters.
    send(d, "другой остаток")
    send(d, "2000")
    assert d._session("u").step is Step.EDIT_CINEMA
    send(d, "500")
    assert d._session("u").profile.balance_cinema == 500


def test_plan_is_reachable_and_disclaims_test_data_without_dead_links():
    d = Dialog(Source())
    start(d)
    send(d, "3000")
    send(d, "без кино")
    finish(d)
    # Match the label, not its decoration: buttons carry a leading icon.
    assert any("собрать план" in b for b in send(d, "не моё").buttons)
    reply = send(d, "собрать план")
    assert "Итого" in reply.text and "остаток" in reply.text
    assert "тестовые" in reply.text and "покупка недоступна" in reply.text
    assert "example.invalid" not in reply.text
    assert "Тест 4" not in reply.text
    assert len(reply.text) < 4000


def test_variable_prices_are_estimates_not_exact_leftover():
    class VariableSource(Source):
        def all_events(self):
            return [replace(e, max_price=2000) for e in super().all_events()]
    d = Dialog(VariableSource())
    start(d)
    send(d, "3000")
    send(d, "без кино")
    finish(d)
    reply = send(d, "/plan")
    assert "Итого от" in reply.text and "остаток до" in reply.text


def test_long_catalogue_records_keep_complete_plans_under_max_limit():
    class LongSource(Source):
        is_synthetic = False

        def all_events(self):
            return [replace(e, name=e.name + "а" * 1000,
                            sale_link="https://example.invalid/" + "x" * 250,
                            is_synthetic=False) for e in super().all_events()]
    d = Dialog(LongSource())
    start(d)
    send(d, "3000")
    send(d, "без кино")
    finish(d)
    reply = send(d, "/plan")
    assert len(reply.text) <= 4000
    assert "Итого" in reply.text and "деньги с карты не списаны" in reply.text


def test_timestamp_stays_at_balance_input_and_survives_restart(tmp_path):
    store = Store(tmp_path / "state.db")
    try:
        d = Dialog(Source(), store)
        start(d)
        send(d, "3000")
        send(d, "без кино")
        finish(d)
        later = datetime(2026, 10, 2, 12)
        send(d, "ещё", later)
        p = store.load_profile("u")
        assert p.balance_reported_at == NOW.isoformat(timespec="seconds")
        resumed = Dialog(Source(), store)
        assert "2026-10-01" in send(resumed, "/balance", later).text
        assert "Итого" in send(resumed, "/plan", later).text
    finally:
        store.close()


def test_editing_balance_does_not_repeat_the_quiz():
    d = Dialog(Source())
    start(d)
    send(d, "3000")
    send(d, "без кино")
    finish(d)
    send(d, "другой остаток")
    send(d, "1500")
    send(d, "0")
    assert d._session("u").step is Step.READY
    assert d._session("u").profile.balance_general == 1500


def test_typing_event_name_does_not_fabricate_buy_click(tmp_path):
    store = Store(tmp_path / "state.db")
    try:
        d = Dialog(Source(), store)
        start(d)
        send(d, "3000")
        send(d, "без кино")
        finish(d)
        send(d, "Тест 1")
        assert store._conn.execute("SELECT count(*) FROM interactions WHERE signal='buy_click'").fetchone()[0] == 0
    finally:
        store.close()
