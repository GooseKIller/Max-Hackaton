"""
The first thing to run when a PRO.Культура.РФ key arrives.

It answers, against real data, the four questions we could not settle with a fixture,
and which the ranking design depends on (see docs/design/ranking.md, "Open questions"):

  1. How reliably is `ageRestriction` populated? If everything is 0+, the audience
     classifier carries the entire load.
  2. How many distinct tags does the Kazan feed actually use? This sizes the whole
     tag-vector approach.
  3. Is there any popularity signal, or is `discovery` purely inverse-frequency?
  4. Is ticket availability exposed? Recommending a sold-out event loses trust fast.

It also prints the real funnel numbers, which replace the synthetic ones on the
evidence slide.

    export PROCULTURE_API_KEY=...
    python3 backend/probe_catalog.py --locales Татарстан    # find the locale ids first
    export PROCULTURE_SUBORDINATIONS=<id>
    python3 backend/probe_catalog.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.catalog import ProCultureError, ProCultureSource, _parse_event  # noqa: E402
from app.config import settings  # noqa: E402
from app.filters import funnel  # noqa: E402
from app.models import UserProfile  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "data"


def find_locales(source: ProCultureSource, query: str) -> None:
    """Discover the locale ids for a region, rather than guessing them."""
    print(f"Searching locales for «{query}»\n")
    for loc in source.locales(query):
        print(f"  _id={loc.get('_id'):<8} {loc.get('name'):<30} {loc.get('sysName', '')}")
    print(
        "\nPut the right id in PROCULTURE_SUBORDINATIONS "
        "(it is recursive — a region id also returns its cities)."
    )


def describe(raw: list[dict]) -> None:
    """The four open questions, answered from real records."""
    n = len(raw)
    if not n:
        print("No events returned. Wrong locale id, or the filters excluded everything.")
        return

    print(f"\n{'=' * 60}\n{n} events returned\n{'=' * 60}")

    # Q1: ageRestriction fill rate
    ages = Counter(r.get("ageRestriction") for r in raw)
    print("\n1. ageRestriction distribution")
    for age, count in sorted(ages.items(), key=lambda kv: (kv[0] is None, kv[0])):
        print(f"   {str(age):>6}+ : {count:>5}  ({count / n:.0%})")
    zero_ish = sum(c for a, c in ages.items() if a in (None, 0))
    print(f"   -> {zero_ish / n:.0%} are 0+ or empty.")
    if zero_ish / n > 0.5:
        print("   -> The age field is mostly useless. The audience classifier is "
              "load-bearing, as suspected.")

    # Q2: tag vocabulary
    tags = Counter()
    for r in raw:
        for t in r.get("tags") or []:
            tags[t.get("name", "?")] += 1
    print(f"\n2. tags: {len(tags)} distinct across {n} events")
    for name, count in tags.most_common(20):
        print(f"   {count:>5}  {name}")
    untagged = sum(1 for r in raw if not r.get("tags"))
    print(f"   -> {untagged} events ({untagged / n:.0%}) carry no tags at all.")

    # Q3 and Q4: what fields actually exist
    keys = Counter()
    for r in raw:
        keys.update(r.keys())
    print("\n3/4. fields present (looking for popularity and availability signals)")
    for key, count in keys.most_common():
        print(f"   {count:>5}  {key}")
    interesting = [
        k for k in keys
        if any(w in k.lower() for w in ("ticket", "avail", "seat", "sold", "view", "rating", "popular"))
    ]
    print(f"   -> candidates for availability/popularity: {interesting or 'none found'}")

    # Prices and categories, for sanity
    prices = [r.get("price") or 0 for r in raw if r.get("price")]
    if prices:
        prices.sort()
        print(f"\nprices: min {prices[0]}, median {prices[len(prices) // 2]}, max {prices[-1]}")
    cats = Counter((r.get("category") or {}).get("name", "?") for r in raw)
    print("categories: " + ", ".join(f"{k} {v}" for k, v in cats.most_common()))


def show_funnel(raw: list[dict]) -> None:
    """The real numbers for the evidence slide."""
    events = [e for e in (_parse_event(r, False) for r in raw) if e is not None]
    print(f"\n{'=' * 60}\nFunnel, for a 16-year-old with 3200 RUB, free evenings and weekends")
    print(f"(parsed {len(events)} of {len(raw)} records)\n")
    user = UserProfile(
        user_id="probe", age=16, balance_general=3200, balance_cinema=2000
    )
    for name, count in funnel(events, user, now=datetime.now()):
        print(f"   {name:<34} {count:>6}")
    print("\nThese replace the synthetic numbers in data/README.md and on the slides.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--locales", metavar="QUERY", help="look up locale ids and exit")
    ap.add_argument("--save", action="store_true", help="save the raw response to data/")
    args = ap.parse_args()

    if not settings.has_proculture_key:
        print("PROCULTURE_API_KEY is not set.")
        print("Put it in .env (see .env.example).")
        print("Still waiting on the key? See docs/outreach/api-key-request.md")
        return 1

    source = ProCultureSource(
        settings.proculture_api_key,
        subordinations=settings.proculture_subordinations or None,
    )

    try:
        if args.locales:
            find_locales(source, args.locales)
            return 0

        if not settings.proculture_subordinations:
            print("PROCULTURE_SUBORDINATIONS is not set — this will fetch ALL of Russia.")
            print("Find the right id first:  python3 backend/probe_catalog.py --locales Татарстан\n")

        print("Fetching… (paging 100 at a time)")
        raw = source.raw_events()
    except ProCultureError as exc:
        print(f"\n{exc}")
        return 1

    describe(raw)
    show_funnel(raw)

    if args.save:
        OUT_DIR.mkdir(exist_ok=True)
        path = OUT_DIR / f"proculture_raw_{datetime.now():%Y%m%d_%H%M}.json"
        path.write_text(
            json.dumps({"_synthetic": False, "events": raw}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        print(f"\nSaved {len(raw)} raw events to {path}")
        print("Point CATALOG_PATH at it to run the bot on real data offline.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
