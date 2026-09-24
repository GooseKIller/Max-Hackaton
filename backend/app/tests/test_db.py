"""
Tests for storage.

The one that matters most is `test_taste_survives_a_restart` — the whole reason the
database exists is that a taste vector used to die with the process, so every
conversation started cold.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.catalog import FixtureSource  # noqa: E402
from app.db import Store  # noqa: E402
from app.dialog import Dialog, Step  # noqa: E402
from app.models import UserProfile  # noqa: E402
from app.taste import Taste  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "data" / "kazan_events.json"


@pytest.fixture
def store(tmp_path) -> Store:
    s = Store(tmp_path / "test.db")
    yield s
    s.close()


@pytest.fixture
def source():
    if not FIXTURE.exists():
        pytest.skip("run data/generate_fixtures.py first")
    return FixtureSource(FIXTURE)


# --- profiles --------------------------------------------------------------


def test_profile_round_trips(store: Store):
    p = UserProfile(
        user_id="u1", age=16, home=(55.79, 49.11), max_km=8.0,
        balance_general=3200, balance_cinema=2000,
        free_evenings=True, free_weekends=False, anchor="Война и мир",
    )
    store.save_profile(p)
    back = store.load_profile("u1")

    assert back is not None
    assert back.age == 16
    assert back.balance_general == 3200
    assert back.free_weekends is False
    assert back.anchor == "Война и мир"
    assert back.home is not None and abs(back.home[0] - 55.79) < 1e-6


def test_unknown_user_is_none(store: Store):
    assert store.load_profile("nobody") is None


def test_saving_twice_updates_rather_than_duplicates(store: Store):
    store.save_profile(UserProfile(user_id="u1", age=16, balance_general=5000))
    store.save_profile(UserProfile(user_id="u1", age=17, balance_general=1000))
    back = store.load_profile("u1")
    assert back.age == 17
    assert back.balance_general == 1000
    assert store.stats()["users"] == 1


# --- taste -----------------------------------------------------------------


def test_taste_round_trips(store: Store):
    t = Taste()
    t.add({"tag:immersivnyy": 1.0, "cat:spektakli": 0.8}, "like")
    store.save_taste("u1", t)

    back = store.load_taste("u1")
    assert back.weights["tag:immersivnyy"] == pytest.approx(1.0)
    assert back.weights["cat:spektakli"] == pytest.approx(0.8)


def test_top_features_reads_like_a_preference_list(store: Store):
    """A taste vector you cannot read is one you cannot explain to a jury."""
    t = Taste()
    t.add({"tag:tehnologii": 1.0}, "buy_click")   # weight 3.0
    t.add({"tag:klassika": 1.0}, "skip")          # negative
    store.save_taste("u1", t)

    top = store.top_features("u1", n=1)
    assert top[0][0] == "tag:tehnologii"


# --- the interaction log ---------------------------------------------------


def test_interactions_accumulate(store: Store):
    store.log("u1", 1, "impression", surface="feed", position=0)
    store.log("u1", 1, "like", surface="quiz")
    store.log("u2", 2, "buy_click")

    assert store.interaction_count("u1") == 2
    assert store.interaction_count() == 3


def test_log_many_is_equivalent(store: Store):
    store.log_many([("u1", i, "impression", "feed", i, None) for i in range(5)])
    assert store.interaction_count("u1") == 5


# --- deletion --------------------------------------------------------------


def test_forget_removes_everything_about_one_person(store: Store):
    store.save_profile(UserProfile(user_id="u1", age=16))
    t = Taste()
    t.add({"tag:x": 1.0}, "like")
    store.save_taste("u1", t)
    store.log("u1", 1, "like")
    store.save_session("u1", "READY", 0, None, [], 0)

    store.save_profile(UserProfile(user_id="u2", age=17))

    store.forget("u1")

    assert store.load_profile("u1") is None
    assert store.load_taste("u1").weights == {}
    assert store.interaction_count("u1") == 0
    assert store.load_session("u1") is None
    assert store.load_profile("u2") is not None, "forgetting one person hit another"


# --- the point of all this -------------------------------------------------


def test_taste_survives_a_restart(store: Store, source):
    """
    The reason this database exists.

    Two Dialog instances over one Store stand in for a process restart: the second
    must pick up where the first left off instead of greeting a stranger.
    """
    first = Dialog(source, store)
    first.handle("u1", "/start")
    first.handle("u1", "16")
    first.handle("u1", "3200")
    first.handle("u1", "вечером и в выходные")
    first.handle("u1", "что-то необычное")
    first.handle("u1", "интересно")

    weights_before = dict(store.load_taste("u1").weights)
    assert weights_before, "nothing was learned from the quiz"

    # A new process, same database.
    second = Dialog(source, store)
    session = second._session("u1")

    assert session.profile.age == 16
    assert session.profile.balance_general == 3200
    assert session.mood == "что-то необычное"
    assert session.step is not Step.NEW, "the conversation restarted from scratch"
    assert session.taste.weights == pytest.approx(weights_before)


def test_a_finished_conversation_keeps_recommending_after_restart(store: Store, source):
    first = Dialog(source, store)
    for msg in ("/start", "16", "3200", "вечером и в выходные", "что-то необычное",
                "пропустить", "пропустить", "пропустить", "пропустить", "пропустить"):
        first.handle("u1", msg)

    second = Dialog(source, store)
    reply = second.handle("u1", "ещё")
    assert "•" in reply.text, "a returning user was not given recommendations"


def test_impressions_are_logged(store: Store, source):
    d = Dialog(source, store)
    for msg in ("/start", "16", "3200", "вечером и в выходные", "что-то необычное",
                "пропустить", "пропустить", "пропустить", "пропустить", "пропустить"):
        d.handle("u1", msg)

    rows = store._conn.execute(
        "SELECT COUNT(*) AS n FROM interactions WHERE signal = 'impression'"
    ).fetchone()["n"]
    assert rows >= 3, "nothing was logged, so no future model can be trained"


def test_labels_are_persisted(store: Store, source):
    Dialog(source, store)
    assert store.stats()["labels"] > 0
