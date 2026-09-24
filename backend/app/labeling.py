"""
Offline labelling: what an event is *about* and how it *feels*.

The API gives us topical tags — «Классика», «Драма», «История». It gives us nothing
about affect, and affect is what a 16-year-old actually chooses on. So we derive it
ourselves.

Two deliberate constraints:

1. **Rules, not a model, for now.** A lexicon over title, description, tags, category
   and venue type. It is deterministic, inspectable, and explains itself when a jury
   asks why something was recommended. An LLM pass can replace or augment this later
   without changing a single caller — see `label_events.py`.

2. **Nothing learned runs at request time.** Per docs/compliance-check.md, labelling
   is an authoring step whose output ships as data. These rules are cheap enough to
   run at load, but the artifact path exists so the upgrade to an LLM or embedding
   labeller costs nothing architecturally.

The six axes come from docs/design/emotional-anchors.md. Each is scored in [-1, 1],
where 0 means "no evidence either way".
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Event

AFFECT_AXES = ("intensity", "valence", "novelty", "social", "effort", "prestige")

# Each axis: (words pushing it up, words pushing it down).
# Matched as substrings against a lowercased blob of title + description + tags,
# so stems rather than whole words.
_LEXICON: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    # calm  <-->  overwhelming
    "intensity": (
        ("иммерсив", "рок", "симфони", "грандиоз", "масштаб", "трагед", "война",
         "реквием", "батл", "экстрим", "оркестр"),
        ("релакс", "медитат", "камерн", "лекци", "тихо", "уютн", "квартирник",
         "аудиогид", "экскурси"),
    ),
    # heavy  <-->  light
    "valence": (
        ("комеди", "смешн", "юмор", "праздник", "карнавал", "мюзикл", "водевиль",
         "весел", "сказк"),
        ("трагед", "памяти", "реквием", "блокад", "репресс", "война", "драм",
         "скорб"),
    ),
    # familiar  <-->  strange
    "novelty": (
        ("иммерсив", "современн", "эксперимент", "необычн", "лаборатор", "медиа",
         "перформанс", "интерактивн", "нестандартн", "индустриальн", "закулис"),
        ("классик", "традицион", "народн", "академическ", "хрестоматийн"),
    ),
    # solitary  <-->  shared
    "social": (
        ("квартирник", "командн", "игра", "квиз", "батл", "вместе", "бал",
         "фестивал", "вечеринк", "клуб"),
        ("выставк", "экспозици", "самостоятельн", "аудиогид", "читальн"),
    ),
    # passive  <-->  participatory
    "effort": (
        ("мастер-класс", "воркшоп", "лаборатор", "практик", "своими руками",
         "интерактивн", "квест", "игра", "репетици", "занятие"),
        ("показ", "концерт", "спектакл", "лекци", "кинопоказ", "сеанс"),
    ),
    # casual  <-->  worth posting about
    "prestige": (
        ("премьер", "уникальн", "впервые", "эксклюзив", "редк", "ночь музеев",
         "закулис", "юбиле", "к 120-лети", "авторск"),
        (),
    ),
}

# Venue and category nudges, applied on top of the lexicon. Weaker than an explicit
# word match, because a category is a much blunter signal than a title.
_CATEGORY_NUDGE: dict[str, dict[str, float]] = {
    "obuchenie": {"effort": 0.5, "novelty": 0.2},
    "ekskursii": {"effort": 0.3, "novelty": 0.2, "social": 0.2},
    "vystavki": {"effort": -0.4, "social": -0.3},
    "kino": {"effort": -0.5, "social": 0.1},
    "koncerty": {"intensity": 0.3, "effort": -0.3},
    "spektakli": {"intensity": 0.2, "effort": -0.3},
    "vstrechi": {"social": 0.4, "effort": 0.2},
    "prazdniki": {"social": 0.5, "valence": 0.4},
}
_PLACE_NUDGE: dict[str, dict[str, float]] = {
    "muzei-i-galerei": {"novelty": 0.1, "social": -0.2},
    "biblioteki": {"intensity": -0.3, "social": -0.1},
    "kinoteatry": {"effort": -0.4},
    "teatry": {"intensity": 0.2},
    "parki": {"social": 0.3, "effort": 0.2},
    "cirki": {"valence": 0.4, "intensity": 0.3},
}


@dataclass(frozen=True)
class EventLabels:
    """What we derived about one event. `why` exists so a human can audit a score."""

    event_id: int
    affect: dict[str, float]
    why: dict[str, list[str]]

    def as_dict(self) -> dict:
        return {"event_id": self.event_id, "affect": self.affect, "why": self.why}


def _blob(event: Event) -> str:
    parts = [event.name, event.short_description, *event.tag_names]
    return " ".join(parts).lower()


def _clamp(x: float) -> float:
    return max(-1.0, min(1.0, x))


def label_event(event: Event) -> EventLabels:
    """Score one event on the six affect axes, and record what drove each score."""
    text = _blob(event)
    affect: dict[str, float] = {}
    why: dict[str, list[str]] = {}

    for axis, (up, down) in _LEXICON.items():
        hits_up = [w for w in up if w in text]
        hits_down = [w for w in down if w in text]
        # Diminishing returns: the third matching word says little the first did not.
        score = 0.45 * len(hits_up) - 0.45 * len(hits_down)
        score = _clamp(score)
        affect[axis] = score
        evidence = [f"+{w}" for w in hits_up] + [f"-{w}" for w in hits_down]
        if evidence:
            why[axis] = evidence

    for axis, delta in _CATEGORY_NUDGE.get(event.category, {}).items():
        affect[axis] = _clamp(affect.get(axis, 0.0) + delta)
        why.setdefault(axis, []).append(f"cat:{event.category}")

    for axis, delta in _PLACE_NUDGE.get(event.place.category, {}).items():
        affect[axis] = _clamp(affect.get(axis, 0.0) + delta)
        why.setdefault(axis, []).append(f"place:{event.place.category}")

    return EventLabels(event_id=event.id, affect=affect, why=why)


def label_all(events: list[Event]) -> dict[int, EventLabels]:
    return {e.id: label_event(e) for e in events}
