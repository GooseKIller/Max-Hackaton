"""
Tests for labelling and ranking.

The point of most of these is to pin down behaviour that is easy to break silently:
a ranker that stops responding to taste, or that quietly serves three copies of the
same show, still returns three plausible-looking events.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.labeling import label_all, label_event  # noqa: E402
from app.models import Event, Place, Seance, UserProfile  # noqa: E402
from app.taste import (  # noqa: E402
    Ranker,
    Taste,
    budget_fit,
    cosine,
    event_vector,
    mood_match,
    quiz_cards,
)

THEATRE = Place("Театр им. Качалова", "teatry", 55.7903, 49.1180, "Баумана, 48")
MUSEUM = Place("Хазинэ", "muzei-i-galerei", 55.7989, 49.1055, "Кремль, 3")
UNIVERSITY = Place("КГЭУ", "obrazovatelnye-uchrezhdeniya", 55.7534, 49.2054, "Красносельская, 51")

SAT_6PM = datetime(2026, 10, 3, 18, 0)
SLOT = Seance(SAT_6PM, SAT_6PM + timedelta(hours=2))


def ev(id: int, name: str, **kw) -> Event:
    base = dict(
        id=id,
        name=name,
        age_restriction=16,
        short_description="",
        category="spektakli",
        tags=(),
        tag_names=(),
        price=500,
        max_price=500,
        sale_link="",
        place=THEATRE,
        seances=(SLOT,),
    )
    base.update(kw)
    return Event(**base)


def teen(**kw) -> UserProfile:
    base = dict(user_id="t", age=16, balance_general=3200, balance_cinema=2000)
    base.update(kw)
    return UserProfile(**base)


# --- affect labelling ------------------------------------------------------


def test_immersive_show_scores_high_on_novelty():
    labels = label_event(ev(1, "Иммерсивный спектакль «Лёгкий человек»"))
    assert labels.affect["novelty"] > 0.3


def test_classic_scores_low_on_novelty():
    labels = label_event(ev(2, "Спектакль по классике, традиционная постановка"))
    assert labels.affect["novelty"] < 0


def test_comedy_is_light_and_tragedy_is_heavy():
    funny = label_event(ev(3, "Комедия «Смешные деньги»"))
    heavy = label_event(ev(4, "Реквием памяти блокады"))
    assert funny.affect["valence"] > heavy.affect["valence"]


def test_workshop_scores_high_on_effort():
    labels = label_event(ev(5, "Мастер-класс по валянию", category="obuchenie"))
    assert labels.affect["effort"] > 0.5


def test_labels_record_their_evidence():
    """A score nobody can explain is a score a jury will not accept."""
    labels = label_event(ev(6, "Иммерсивный перформанс"))
    assert labels.why.get("novelty")
    assert any("иммерсив" in w for w in labels.why["novelty"])


# --- vectors ---------------------------------------------------------------


def test_similar_events_are_close_and_different_ones_are_not():
    a = event_vector(ev(1, "A", tags=("immersivnyy", "tanec")))
    b = event_vector(ev(2, "B", tags=("immersivnyy", "tanec")))
    c = event_vector(ev(3, "C", tags=("klassika",), category="koncerty", place=MUSEUM))
    assert cosine(a, b) > cosine(a, c)


def test_cosine_of_empty_vector_is_zero():
    assert cosine({}, {"tag:x": 1.0}) == 0.0


def test_taste_starts_cold_and_warms_up():
    t = Taste()
    assert t.is_cold
    t.add(event_vector(ev(1, "A", tags=("tanec",))), "like")
    assert not t.is_cold


def test_dislike_pushes_taste_the_other_way():
    liked = event_vector(ev(1, "A", tags=("tanec",)))
    t = Taste()
    t.add(liked, "dislike")
    assert t.weights["tag:tanec"] < 0


# --- money -----------------------------------------------------------------


def test_budget_fit_prefers_using_a_meaningful_share():
    user = teen(balance_general=3000)
    good = budget_fit(ev(1, "A", price=1200), user)   # 40% of what is left
    stub = budget_fit(ev(2, "B", price=100), user)    # leaves an awkward remainder
    assert good > stub


def test_unaffordable_scores_zero():
    assert budget_fit(ev(1, "A", price=9999), teen()) == 0.0


def test_cinema_uses_the_cinema_pool():
    user = teen(balance_general=3200, balance_cinema=0)
    assert budget_fit(ev(1, "Фильм", category="kino", price=300), user) == 0.0


# --- ranking ---------------------------------------------------------------


def _catalogue() -> list[Event]:
    return [
        ev(1, "Спектакль «Женитьба»", tags=("klassika", "drama")),
        ev(2, "Спектакль «Ревизор»", tags=("klassika", "drama")),
        ev(3, "Спектакль «Гроза»", tags=("klassika", "drama")),
        ev(4, "Иммерсивный спектакль «Лёгкий человек»", tags=("immersivnyy", "sovremennoe-iskusstvo")),
        ev(5, "Мастер-класс по аналоговой фотографии",
           tags=("master-klass", "fotografiya"), category="obuchenie", place=UNIVERSITY),
        ev(6, "Индустриальная экскурсия «Ток бежит по проводам»",
           tags=("tehnologii", "nauka"), category="ekskursii", place=UNIVERSITY),
    ]


def _ranker(events: list[Event]) -> Ranker:
    return Ranker(events, label_all(events))


def test_taste_changes_the_order():
    events = _catalogue()
    r = _ranker(events)
    pairs = [(e, SLOT) for e in events]

    likes_workshops = Taste()
    likes_workshops.add(event_vector(events[4]), "like")
    likes_workshops.add(event_vector(events[5]), "like")

    top = r.score(pairs, teen(), likes_workshops, today=date(2026, 10, 1))[0]
    assert top.event.id in (5, 6)


def test_diversify_does_not_return_three_of_the_same_kind():
    events = _catalogue()
    r = _ranker(events)
    pairs = [(e, SLOT) for e in events]

    likes_classics = Taste()
    likes_classics.add(event_vector(events[0]), "like")

    picked = r.recommend(pairs, teen(), likes_classics, n=3, today=date(2026, 10, 1))
    tags = {t for p in picked for t in p.event.tags}
    assert len(tags) > 2, "all three picks came from the same corner of the catalogue"


def test_duplicate_titles_are_collapsed():
    """The same production runs many times; showing it twice reads as broken."""
    events = [ev(1, "Спектакль «Женитьба»"), ev(2, "Спектакль «Женитьба»"), ev(3, "Другое")]
    r = _ranker(events)
    picked = r.recommend([(e, SLOT) for e in events], teen(), Taste(), n=3,
                         today=date(2026, 10, 1))
    names = [p.event.name for p in picked]
    assert len(names) == len(set(names))


def test_every_pick_can_explain_itself():
    events = _catalogue()
    r = _ranker(events)
    picked = r.recommend([(e, SLOT) for e in events], teen(), Taste(), n=3,
                         today=date(2026, 10, 1))
    for p in picked:
        assert p.top_reason() in {"taste", "discovery", "budget", "convenience", "urgency"}


# --- mood ------------------------------------------------------------------


def test_mood_match_detects_a_miss():
    """
    Asking for something funny and being handed a requiem should register as a miss,
    so the bot can say so instead of pretending.
    """
    events = [ev(1, "Реквием памяти")]
    labels = label_all(events)
    vectors = [event_vector(events[0], labels[1])]
    assert mood_match(vectors, "что-нибудь смешное") < 0.15


def test_mood_match_detects_a_hit():
    events = [ev(1, "Комедия «Смешные деньги»", category="prazdniki")]
    labels = label_all(events)
    vectors = [event_vector(events[0], labels[1])]
    assert mood_match(vectors, "что-нибудь смешное") > 0.15


# --- onboarding ------------------------------------------------------------


def test_quiz_cards_span_the_catalogue():
    """A card that tells us nothing new is a wasted question."""
    events = _catalogue()
    r = _ranker(events)
    cards = quiz_cards(events, r, n=4)
    assert len(cards) == 4
    assert len({c.id for c in cards}) == 4
    tags = {t for c in cards for t in c.tags}
    assert len(tags) >= 4, "the quiz only probes one corner of the feature space"
