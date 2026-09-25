"""
Settings and, more importantly, the Pushkin Card rules.

The card rules live here as DATA, not scattered through the code, because they are
policy that may change. The brief also scores us on showing the user
where a number came from and when it was last checked — so every rule carries its
source and an as-of date, and the UI is expected to surface them.

Never hardcode a limit anywhere else in this codebase.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CardRules:
    """
    The Pushkin Card limits, as of a stated date, from a stated source.

    `total` is the annual amount. `cinema_cap` is the part of it that may be spent
    on cinema — it is a sub-limit inside `total`, not money on top of it. So the
    amount available for everything else is `total - cinema_spent`, capped only by
    what is left overall.
    """

    total: int
    cinema_cap: int
    as_of: str
    source: str
    note: str = ""

    def pools(self, spent_cinema: int, spent_other: int) -> tuple[int, int]:
        """
        Remaining money, as (general, cinema).

        `general` is what can go to non-cinema events; `cinema` is what can still go
        to cinema, which is bounded both by the cinema sub-limit and by the total.
        """
        left_total = max(0, self.total - spent_cinema - spent_other)
        left_cinema = min(left_total, max(0, self.cinema_cap - spent_cinema))
        return left_total, left_cinema


# Official programme page, rechecked 25 September 2026. Proposals reported by
# media are not enacted rules; verify the official source before the pilot.
CARD_RULES_2026 = CardRules(
    total=5_000,
    cinema_cap=2_000,
    as_of="2026-09-25",
    source="https://www.culture.ru/pushkinskaya-karta",
    note=(
        "Общий лимит 5000 ₽; до 2000 ₽ внутри него на кино. "
        "Остатки вводит пользователь; перед запуском проверьте актуальные правила."
    ),
)

# The balance expires at the end of the calendar year and does not roll over.
BALANCE_EXPIRES = "2026-12-31"

ELIGIBLE_AGE_MIN = 14
ELIGIBLE_AGE_MAX = 22


@dataclass(frozen=True)
class Settings:
    max_bot_token: str = field(default_factory=lambda: os.getenv("MAX_BOT_TOKEN", ""))
    max_api_base: str = field(
        default_factory=lambda: os.getenv("MAX_API_BASE", "https://platform-api2.max.ru")
    )
    catalog_path: str = field(
        default_factory=lambda: os.getenv("CATALOG_PATH", "data/kazan_events.json")
    )
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "data/app.db"))
    proculture_api_key: str = field(
        default_factory=lambda: os.getenv("PROCULTURE_API_KEY", "")
    )
    # Locale ids for the region we serve. Left empty on purpose: discover them once
    # with a real key (`python3 backend/probe_catalog.py --locales Татарстан`) and
    # pin the result here rather than guessing and silently serving another region.
    proculture_subordinations: str = field(
        default_factory=lambda: os.getenv("PROCULTURE_SUBORDINATIONS", "")
    )
    city_centre: tuple[float, float] = (55.7963, 49.1088)  # Kazan Kremlin
    default_max_km: float = 10.0
    results_shown: int = 3

    @property
    def has_max_token(self) -> bool:
        return bool(self.max_bot_token)

    @property
    def has_proculture_key(self) -> bool:
        return bool(self.proculture_api_key)


settings = Settings()
