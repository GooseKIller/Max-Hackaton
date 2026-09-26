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
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path | None = None) -> None:
    """
    Read `.env` into the process environment, if it is there.

    Every document tells the reader to put their token in `.env`, and until this
    existed nothing actually read it: `os.getenv` sees the process environment, and
    only Docker Compose was loading `env_file` on its own. So `console.py`,
    `runner.py` and `check_token.py` all reported "MAX_BOT_TOKEN is not set" at a
    user who had just set it.

    Written by hand rather than adding python-dotenv: it is fifteen lines, and one
    fewer pinned dependency is one fewer thing in the image.

    A real environment variable always wins, so Docker, CI and `FOO=bar python ...`
    keep overriding the file.
    """
    path = path or _REPO_ROOT / ".env"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


load_dotenv()


# --- TLS -------------------------------------------------------------------

RU_TRUSTED_ROOT = _REPO_ROOT / "certs" / "russian-trusted-root-ca.pem"


def ssl_context():
    """
    A TLS context that also trusts the Russian Trusted Root CA.

    `platform-api2.max.ru` presents a certificate chained to
    "The Ministry of Digital Development and Communications — Russian Trusted Root
    CA". That root ships in neither certifi nor the default macOS/Linux trust
    stores, so a stock Python client fails with CERTIFICATE_VERIFY_FAILED before it
    can even send the token. Browsers in Russia usually have it preinstalled, which
    is why the API looks fine in a browser and dies in code.

    This **adds** that one root to the normal public bundle; it does not replace it
    and it does not disable verification. Every other host still verifies exactly as
    before, and a bad certificate on max.ru is still rejected.

    `verify=False` would also have made the error go away. It would also have made
    the connection unauthenticated, which is not a trade worth making for a bot that
    carries a token.
    """
    import ssl

    import certifi

    context = ssl.create_default_context(cafile=certifi.where())
    if RU_TRUSTED_ROOT.exists():
        context.load_verify_locations(cafile=str(RU_TRUSTED_ROOT))
    return context


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
    # Closed by default. Register the same secret with MAX before enabling webhook.
    max_webhook_secret: str = field(default_factory=lambda: os.getenv("MAX_WEBHOOK_SECRET", ""))
    mini_app_bot: str = field(default_factory=lambda: os.getenv("MINI_APP_BOT", ""))
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
