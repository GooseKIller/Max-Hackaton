"""
Tests for the timing signals.

The asymmetry between a fast no and a slow no is the whole point of this module,
and it is the kind of thing that gets "simplified" away by someone who reads the
code and not the reasoning. These tests state it as a requirement.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.timing import (  # noqa: E402
    ABANDON_MS,
    BASELINE_MIN_SAMPLES,
    baseline,
    Timing,
    confidence,
    fatigue,
    free_time_evidence,
    weight,
)


def t(ms: int | None, position: int = 0) -> Timing:
    return Timing(latency_ms=ms, position=position)


# --- the asymmetry ---------------------------------------------------------


def test_a_slow_no_counts_for_less_than_a_fast_no():
    """
    Considering an event and still declining it is a no about *that event*, not
    about its kind. Recording it at full weight teaches the ranker to avoid the
    very things the person was drawn to.
    """
    assert confidence("dislike", t(6_000)) < confidence("dislike", t(2_000))


def test_a_fast_no_is_taken_at_face_value():
    assert confidence("dislike", t(2_000)) == 1.0


def test_a_slow_yes_counts_for_less_than_a_fast_yes():
    assert confidence("like", t(6_000)) < confidence("like", t(2_000))


def test_reflex_taps_are_damped_whichever_way_they_go():
    """Under a second nobody has read a venue name. That is a thumb, not a taste."""
    assert confidence("like", t(300)) < 1.0
    assert confidence("dislike", t(300)) < 1.0


# --- walking away ----------------------------------------------------------


def test_putting_the_phone_down_is_not_deliberation():
    """
    Without a cap, an overnight pause would read as the most considered decision
    anyone ever made.
    """
    overnight = t(ABANDON_MS * 100)
    assert overnight.is_abandoned
    assert not overnight.is_considered
    assert confidence("dislike", overnight) == 1.0


def test_unknown_latency_changes_nothing():
    """The first message of a session has nothing to measure against."""
    assert confidence("like", t(None)) == 1.0
    assert confidence("dislike", t(None)) == 1.0


# --- fatigue ---------------------------------------------------------------


def test_late_swipes_count_for_less():
    """One bored evening must not overwrite a taste built over weeks."""
    assert fatigue(40) < fatigue(15) < fatigue(3)


def test_weight_combines_confidence_and_fatigue():
    early_considered = weight("dislike", t(6_000, position=1))
    late_considered = weight("dislike", t(6_000, position=40))
    assert late_considered < early_considered


# --- when someone is actually free -----------------------------------------


def test_usage_hours_reveal_when_someone_is_free():
    """
    Onboarding asks people to predict their own schedule. When they open the bot
    is evidence. Someone swiping at 22:40 on a Tuesday is not free at 10:00 on a
    Tuesday, whatever they ticked.
    """
    moments = [
        datetime(2026, 10, 6, 22, 40),   # Tue evening
        datetime(2026, 10, 7, 23, 10),   # Wed evening
        datetime(2026, 10, 10, 14, 0),   # Sat afternoon
        datetime(2026, 10, 8, 9, 30),    # Thu morning
    ]
    counts = free_time_evidence(moments)
    assert counts["weekday_evening"] == 2
    assert counts["weekend"] == 1
    assert counts["weekday_daytime"] == 1


def test_no_usage_yields_no_claims():
    assert free_time_evidence([]) == {
        "weekday_daytime": 0,
        "weekday_evening": 0,
        "weekend": 0,
    }


# --- relative, not absolute ------------------------------------------------


def rel(ms: int, base: int | None) -> Timing:
    return Timing(latency_ms=ms, position=0, baseline_ms=base)


def test_a_fast_person_is_not_permanently_treated_as_reflexive():
    """
    Someone who answers every card in a second is not being thoughtless — that is
    their pace. Judged against a fixed 1.2s threshold, every answer they ever give
    is damped to 0.6.
    """
    fast_person = rel(900, base=800)          # normal *for them*
    assert not fast_person.is_reflex
    assert confidence("dislike", fast_person) == 1.0

    # The same 900ms from someone who usually takes six seconds IS a reflex.
    slow_person = rel(900, base=6_000)
    assert slow_person.is_reflex


def test_a_slow_person_does_not_have_every_rejection_damped():
    """
    Someone whose normal pace is ten seconds is not deliberating over every card.
    Absolutely, every one of their answers clears the 4s "considered" bar.
    """
    slow_person = rel(9_000, base=10_000)     # normal for them
    assert not slow_person.is_considered
    assert confidence("dislike", slow_person) == 1.0

    really_considered = rel(25_000, base=10_000)
    assert really_considered.is_considered
    assert confidence("dislike", really_considered) < 1.0


def test_absolute_thresholds_are_used_until_a_baseline_exists():
    """A new user has no pace of their own yet, so the generic numbers apply."""
    assert rel(500, base=None).is_reflex
    assert rel(8_000, base=None).is_considered


def test_a_baseline_needs_enough_samples():
    assert baseline([1000, 1000]) is None
    assert baseline([1000] * BASELINE_MIN_SAMPLES) == 1000


def test_a_baseline_ignores_walking_away():
    """One overnight pause must not redefine someone's reading speed."""
    with_pause = [1000, 1100, 900, 1000, 1200, ABANDON_MS * 50]
    assert baseline(with_pause) is not None
    assert baseline(with_pause) < 2000


def test_walking_away_is_absolute_at_any_pace():
    """A two-minute gap is someone leaving, however slowly they normally read."""
    assert rel(ABANDON_MS + 1, base=30_000).is_abandoned
