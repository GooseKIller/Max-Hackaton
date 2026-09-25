"""Bounded 2–3-event plans over ranked candidates; no payment or booking implied.

Prices are catalogue lower bounds. Plans are estimates until seats/prices are checked
at the seller. We search the top 30 distinct events, each at its supplied showtime,
not every event/showtime in the city. The caller applies age/time/location filters.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from itertools import combinations

from .config import BALANCE_EXPIRES, CARD_RULES_2026
from .filters import affordable
from .models import UserProfile
from .taste import Scored


@dataclass(frozen=True)
class Plan:
    kind: str
    items: tuple[Scored, ...]
    total: int
    cinema_total: int
    remaining: int


def build_plans(
    ranked: list[Scored], user: UserProfile, *, max_candidates: int = 30,
    transfer_minutes: int = 45,
) -> list[Plan]:
    """Return distinct relevant/diverse/budget alternatives, or an honest empty list.

    The fixed transfer buffer avoids back-to-back shows but is not a route estimate.
    Missing/invalid end times cannot support a schedule, so such slots are excluded.
    The year-end cutoff is our planning horizon, not a claim about ticket sale rules.
    """
    if user.balance_general is None or user.balance_general <= 0:
        return []
    if not 2 <= max_candidates <= 30 or transfer_minutes < 0:
        raise ValueError("use 2–30 candidates and a non-negative transfer buffer")
    horizon = date.fromisoformat(BALANCE_EXPIRES)
    shortlist: list[Scored] = []
    seen: set[int] = set()
    seen_productions: set[tuple[str, str]] = set()
    for item in ranked:
        production = (item.event.name.strip().casefold(), item.event.place.name.strip().casefold())
        if item.event.id in seen or production in seen_productions or not affordable(item.event, user):
            continue
        if item.seance.end <= item.seance.start or item.seance.end.date() > horizon:
            continue
        seen.add(item.event.id)
        seen_productions.add(production)
        shortlist.append(item)
        if len(shortlist) == max_candidates:
            break

    feasible: list[tuple[tuple[Scored, ...], int, int, float, int]] = []
    buffer = timedelta(minutes=transfer_minutes)
    for size in (2, 3):
        for group in combinations(shortlist, size):
            total = sum(s.event.price for s in group)
            if total > user.balance_general:
                continue
            cinema = sum(s.event.price for s in group if s.event.is_cinema)
            if cinema > min(user.balance_cinema or 0, CARD_RULES_2026.cinema_cap):
                continue
            ordered = tuple(sorted(group, key=lambda s: (s.seance.start, s.event.id)))
            if any(a.seance.end + buffer > b.seance.start
                   for a, b in zip(ordered, ordered[1:])):
                continue
            quality = sum(s.score for s in group) / size
            diversity = len({s.event.category for s in group})
            feasible.append((ordered, total, cinema, quality, diversity))

    result: list[Plan] = []
    used: set[tuple[int, ...]] = set()
    for kind in ("interests", "variety", "budget"):
        choices = [p for p in feasible if tuple(sorted(s.event.id for s in p[0])) not in used]
        if kind == "variety":
            choices = [p for p in choices if p[4] >= 2]
        if not choices:
            continue
        if kind == "budget":
            chosen = max(choices, key=lambda p: (p[1], p[3], p[4]))
        elif kind == "variety":
            chosen = max(choices, key=lambda p: (p[4], p[3], p[1]))
        else:
            chosen = max(choices, key=lambda p: (p[3], p[4], p[1]))
        items, total, cinema, _, _ = chosen
        used.add(tuple(sorted(s.event.id for s in items)))
        result.append(Plan(kind, items, total, cinema, user.balance_general - total))
    return result
