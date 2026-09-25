"""
Hard filters: step 1 of the ranking plan in docs/design/ranking.md.

These eliminate, they do not score. Everything that survives here is something the
user could actually attend and pay for. Ranking between the survivors is a separate
job, deliberately not done in this module.

Measured on the synthetic Kazan catalogue, these remove about half of it — and
crucially, the legal age check on its own removes nothing at all.
"""

from __future__ import annotations

from datetime import datetime
from math import asin, cos, radians, sin, sqrt

from .models import Event, Seance, UserProfile

# Words that give away an event aimed at small children, regardless of what
# `ageRestriction` says. Derived from the live Kazan listing.
_SMALL_CHILD_MARKERS = (
    "бэби", "беби", "baby",
    "для самых маленьких", "для малышей",
    "азбука", "сказка", "кукольный",
    "утренник", "сенсорн",
)


def km_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in km. Good enough for 'is it across town'."""
    lat1, lon1, lat2, lon2 = map(radians, (a[0], a[1], b[0], b[1]))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * asin(sqrt(h))


def is_for_small_children(event: Event) -> bool:
    """
    Is this really aimed at small children?

    `ageRestriction` cannot answer this. It is a legal *minimum*: a baby concert is
    0+, and 0 <= 16, so a naive age check lets it through. This is exactly the bug
    visible on the official listing, where «Беби-концерт» appears under the
    "Для молодежи" filter.

    So we infer the target audience separately, from the title and from the shape of
    the event. Rules first; a learned classifier can replace this later without
    changing anything that calls it.
    """
    title = event.name.lower()
    if any(marker in title for marker in _SMALL_CHILD_MARKERS):
        return True
    # A 0+/6+ staged show in a theatre is a children's show.
    if event.age_restriction <= 6 and event.place.category == "teatry":
        return True
    return False


def is_reachable_time(seance: Seance, user: UserProfile) -> bool:
    """
    Can this person actually be there?

    A large share of the catalogue happens on weekday mornings at schools, libraries
    and colleges — those are organised group visits booked by a teacher, not options
    for someone choosing for themselves.
    """
    if seance.is_weekend:
        return user.free_weekends and seance.start.hour >= 9
    return user.free_evenings and seance.start.hour >= 16


def affordable(event: Event, user: UserProfile) -> bool:
    """Unknown total permits browsing, not a funded plan; unknown cinema excludes it."""
    if event.price < 0:
        return False
    if user.balance_general is not None and event.price > user.balance_general:
        return False
    if event.is_cinema:
        from .config import CARD_RULES_2026

        return (
            user.balance_cinema is not None
            and event.price <= min(user.balance_cinema, CARD_RULES_2026.cinema_cap)
        )
    return True


def usable_seances(event: Event, user: UserProfile, now: datetime) -> list[Seance]:
    """Showtimes that are in the future and at a time this person is free."""
    return [
        s
        for s in event.seances
        if s.start > now and is_reachable_time(s, user)
    ]


def candidates(
    events: list[Event],
    user: UserProfile,
    now: datetime | None = None,
) -> list[tuple[Event, Seance]]:
    """
    The survivors, each paired with its soonest usable showtime.

    Returned in chronological order — that is NOT a ranking, just a stable default.
    Ranking is the next step and lives elsewhere.
    """
    now = now or datetime.now()
    out: list[tuple[Event, Seance]] = []

    for event in events:
        if user.age is not None and event.age_restriction > user.age:
            continue
        if is_for_small_children(event):
            continue
        if not affordable(event, user):
            continue
        if user.home is not None:
            if km_between(user.home, (event.place.lat, event.place.lon)) > user.max_km:
                continue
        slots = usable_seances(event, user, now)
        if not slots:
            continue
        out.append((event, slots[0]))

    out.sort(key=lambda pair: pair[1].start)
    return out


def funnel(
    events: list[Event],
    user: UserProfile,
    now: datetime | None = None,
) -> list[tuple[str, int]]:
    """
    The same filters, reported stage by stage.

    Useful for the evidence slide and for spotting when a filter silently removes
    everything. Kept beside the filters themselves so the two cannot drift apart.
    """
    now = now or datetime.now()
    stages: list[tuple[str, int]] = [("всего в каталоге", len(events))]

    survivors = [
        e for e in events if user.age is None or e.age_restriction <= user.age
    ]
    stages.append(("проходят по возрастному цензу", len(survivors)))

    survivors = [e for e in survivors if not is_for_small_children(e)]
    stages.append(("не для маленьких детей", len(survivors)))

    survivors = [e for e in survivors if usable_seances(e, user, now)]
    stages.append(("идут, когда ты свободен", len(survivors)))

    survivors = [e for e in survivors if affordable(e, user)]
    stages.append(("влезают в остаток", len(survivors)))

    if user.home is not None:
        survivors = [
            e for e in survivors
            if km_between(user.home, (e.place.lat, e.place.lon)) <= user.max_km
        ]
        stages.append(("можно доехать", len(survivors)))

    return stages
