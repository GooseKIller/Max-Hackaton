"""
Domain models.

These mirror the PRO.Культура.РФ API 2.5 `pushkinsCardEvents` shape, because that is
the real feed we intend to use. Everything above this layer works with these objects
and never touches raw JSON, so swapping the fixture for the live API changes only the
parsing in `catalog.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Seance:
    """One showtime."""

    start: datetime
    end: datetime

    @property
    def is_weekend(self) -> bool:
        return self.start.weekday() >= 5


@dataclass(frozen=True)
class Place:
    name: str
    category: str          # sysName: teatry, muzei-i-galerei, biblioteki, ...
    lat: float
    lon: float
    address: str


@dataclass(frozen=True)
class Event:
    id: int
    name: str
    age_restriction: int            # legal minimum age, NOT the target audience
    short_description: str
    category: str                   # sysName: spektakli, koncerty, kino, ...
    tags: tuple[str, ...]           # sysNames
    tag_names: tuple[str, ...]
    price: int
    max_price: int
    sale_link: str
    place: Place
    seances: tuple[Seance, ...]
    is_synthetic: bool = False

    @property
    def is_cinema(self) -> bool:
        """Cinema must fit both the total balance and its remaining sub-limit."""
        return self.category == "kino"

    def next_seance_after(self, moment: datetime) -> Seance | None:
        for s in sorted(self.seances, key=lambda s: s.start):
            if s.start > moment:
                return s
        return None


@dataclass
class UserProfile:
    """
    What we know about one person.

    `balance_*` is user-reported: there is no public API for the Pushkin Card
    balance, so we ask and we label it as their own number rather than pretending
    it is verified.
    """

    user_id: str
    age: int | None = None
    home: tuple[float, float] | None = None
    max_km: float = 10.0
    balance_general: int | None = None
    balance_cinema: int | None = None
    balance_reported_at: str | None = None
    free_evenings: bool = True
    free_weekends: bool = True
    anchor: str | None = None           # "what got you recently" — see design/emotional-anchors.md
    seen_event_ids: set[int] = field(default_factory=set)

    @property
    def is_onboarded(self) -> bool:
        return self.age is not None and self.balance_general is not None
