"""
Tests for the hard filters.

The first test is the important one: it pins down the bug this whole product exists
to fix. If someone ever "simplifies" the audience check down to `ageRestriction`,
that test fails and explains why.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.filters import (  # noqa: E402
    affordable,
    candidates,
    is_for_small_children,
    is_reachable_time,
    km_between,
)
from app.models import Event, Place, Seance, UserProfile  # noqa: E402

KAZAN = Place(
    name="Татарский государственный академический театр кукол «Экият»",
    category="teatry",
    lat=55.7723,
    lon=49.1301,
    address="Петербургская, 57",
)
MUSEUM = Place(
    name="Национальная художественная галерея «Хазинэ»",
    category="muzei-i-galerei",
    lat=55.7989,
    lon=49.1055,
    address="Кремль, 3",
)

MONDAY_10AM = datetime(2026, 10, 5, 10, 0)
SATURDAY_6PM = datetime(2026, 10, 3, 18, 0)
MONDAY_7PM = datetime(2026, 10, 5, 19, 0)


def make_event(**kw) -> Event:
    base = dict(
        id=1,
        name="Событие",
        age_restriction=0,
        short_description="",
        category="spektakli",
        tags=(),
        tag_names=(),
        price=300,
        max_price=300,
        sale_link="https://example.invalid/1",
        place=MUSEUM,
        seances=(Seance(start=SATURDAY_6PM, end=SATURDAY_6PM + timedelta(hours=2)),),
    )
    base.update(kw)
    return Event(**base)


def teen(**kw) -> UserProfile:
    base = dict(
        user_id="t",
        age=16,
        balance_general=3200,
        balance_cinema=2000,
    )
    base.update(kw)
    return UserProfile(**base)


# --- the bug this product exists to fix -----------------------------------


def test_baby_concert_passes_the_legal_age_check():
    """
    A baby concert is 0+, and 0 <= 16, so the legal age check lets it through.

    This is not a bug in our code — it is the reason the official listing shows
    «Беби-концерт» under its "Для молодежи" filter. Pinned here so nobody
    "simplifies" the audience check into an age comparison.
    """
    baby = make_event(name="Программа «Беби-концерт»", age_restriction=0)
    assert baby.age_restriction <= 16          # the naive check says yes
    assert is_for_small_children(baby)         # ours says no


def test_puppet_show_in_a_theatre_is_for_children():
    show = make_event(name="Спектакль «Гуси-лебеди»", age_restriction=6, place=KAZAN)
    assert is_for_small_children(show)


def test_adult_drama_in_the_same_theatre_is_not():
    show = make_event(name="Спектакль «Женитьба»", age_restriction=16, place=KAZAN)
    assert not is_for_small_children(show)


def test_immersive_show_survives():
    show = make_event(name="Иммерсивный спектакль «Лёгкий человек»", age_restriction=16)
    assert not is_for_small_children(show)


# --- time -----------------------------------------------------------------


def test_weekday_morning_is_not_reachable():
    """Weekday-daytime events are organised school trips, not real options."""
    s = Seance(start=MONDAY_10AM, end=MONDAY_10AM + timedelta(hours=1))
    assert not is_reachable_time(s, teen())


def test_weekday_evening_is_reachable():
    s = Seance(start=MONDAY_7PM, end=MONDAY_7PM + timedelta(hours=2))
    assert is_reachable_time(s, teen())


def test_weekend_afternoon_is_reachable():
    s = Seance(start=SATURDAY_6PM, end=SATURDAY_6PM + timedelta(hours=2))
    assert is_reachable_time(s, teen())


def test_weekends_only_user_skips_weekday_evenings():
    s = Seance(start=MONDAY_7PM, end=MONDAY_7PM + timedelta(hours=2))
    assert not is_reachable_time(s, teen(free_evenings=False))


# --- money: two pools, not one --------------------------------------------


def test_cinema_draws_on_the_cinema_pool():
    user = teen(balance_general=3200, balance_cinema=0)
    film = make_event(category="kino", price=400)
    assert not affordable(film, user)


def test_non_cinema_is_unaffected_by_an_empty_cinema_pool():
    user = teen(balance_general=3200, balance_cinema=0)
    play = make_event(category="spektakli", price=400)
    assert affordable(play, user)


def test_too_expensive_is_rejected():
    assert not affordable(make_event(price=4000), teen())


# --- distance -------------------------------------------------------------


def test_distance_is_roughly_right():
    # Kremlin to the puppet theatre is about 3 km across the centre.
    d = km_between((55.7963, 49.1088), (KAZAN.lat, KAZAN.lon))
    assert 1.5 < d < 5.0


def test_far_venue_is_excluded():
    far = Place(name="Далеко", category="prochee", lat=56.5, lon=49.1, address="")
    user = teen(home=(55.7963, 49.1088), max_km=8)
    assert candidates([make_event(place=far)], user, now=datetime(2026, 10, 1)) == []


# --- the whole funnel -----------------------------------------------------


def test_candidates_pairs_each_event_with_its_soonest_usable_slot():
    event = make_event(
        age_restriction=16,
        seances=(
            Seance(start=MONDAY_10AM, end=MONDAY_10AM + timedelta(hours=1)),   # unusable
            Seance(start=MONDAY_7PM, end=MONDAY_7PM + timedelta(hours=2)),     # usable
        ),
    )
    found = candidates([event], teen(), now=datetime(2026, 10, 1))
    assert len(found) == 1
    assert found[0][1].start == MONDAY_7PM


def test_past_events_are_dropped():
    event = make_event(age_restriction=16)
    assert candidates([event], teen(), now=datetime(2026, 12, 1)) == []
