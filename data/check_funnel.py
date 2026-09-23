"""
Sanity-check the fixture catalogue by running the hard-filter funnel over it.

This is not product code — it is the measurement that backs our core claim:
that a teenager choosing for themselves faces a catalogue where most of the
nominal supply is unreachable or irrelevant, and that plain deterministic
filters (no ML at all) do most of the work.

The numbers this prints are the ones that belong on the evidence slide, with the
caveat that they come from synthetic data until the API key arrives.

Run:  python3 data/check_funnel.py
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

DATA = Path(__file__).parent / "kazan_events.json"
LABELS = Path(__file__).parent / "kazan_events_labels.json"

# A concrete user, so the numbers mean something.
USER = {
    "age": 16,
    "home": (55.8271, 49.0703),   # near Восстания
    "max_km": 8.0,
    "balance_general": 3200,       # RUB left outside the cinema pool
    "balance_cinema": 0,           # cinema pool already spent — the common case
    "free": "evenings_and_weekends",
}


def km_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (a[0], a[1], b[0], b[1]))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * asin(sqrt(h))


def is_free_time(when: datetime) -> bool:
    """When is a school student actually able to go?"""
    if when.weekday() >= 5:
        return when.hour >= 9
    return when.hour >= 16


def looks_like_small_children(event: dict) -> bool:
    """
    Target-audience heuristic. `ageRestriction` is a legal minimum, not an
    audience: a baby concert is 0+, and 0 <= 16, so a naive age filter keeps it.
    This is the bug we found on the live official listing, where «Беби-концерт»
    appears under the "Для молодежи" filter.
    """
    title = event["name"].lower()
    kid_words = ("бэби", "беби", "для самых маленьких", "азбука", "сказка",
                 "кукольный", "сенсорн", "зайчик", "медвед")
    if any(w in title for w in kid_words):
        return True
    if event["ageRestriction"] <= 6:
        place_kind = event["places"][0]["category"]["sysName"]
        # A 0+/6+ show staged in a theatre is a children's show. The age field
        # cannot tell us this on its own — 0 <= 16 passes any naive filter.
        if place_kind == "teatry":
            return True
    return False


def main() -> None:
    blob = json.loads(DATA.read_text(encoding="utf-8"))
    events = blob["events"]
    labels = {l["_id"]: l for l in json.loads(LABELS.read_text(encoding="utf-8"))["labels"]}

    if blob.get("_synthetic"):
        print("!! SYNTHETIC DATA — these numbers are indicative, not evidence.\n")

    # The funnel. Each stage is a strict subset of the one above it.
    stages: list[tuple[str, int]] = []
    survivors = events
    stages.append(("everything in the catalogue", len(survivors)))

    # 1. Age: the legal minimum must allow them in.
    survivors = [e for e in survivors if e["ageRestriction"] <= USER["age"]]
    stages.append(("legal age allows them in", len(survivors)))

    # 2. Audience: not actually aimed at small children.
    survivors = [e for e in survivors if not looks_like_small_children(e)]
    stages.append(("not aimed at small children", len(survivors)))

    # 3. Time: at least one showtime when they are free.
    def has_free_slot(e: dict) -> bool:
        return any(
            is_free_time(datetime.fromisoformat(s["startLocal"]))
            for s in e["places"][0]["seances"]
        )

    survivors = [e for e in survivors if has_free_slot(e)]
    stages.append(("happens when they are free", len(survivors)))

    # 4. Budget, in the right pool.
    def affordable(e: dict) -> bool:
        pool = (USER["balance_cinema"] if e["category"]["sysName"] == "kino"
                else USER["balance_general"])
        return e["price"] <= pool

    survivors = [e for e in survivors if affordable(e)]
    stages.append(("fits the remaining balance", len(survivors)))

    # 5. Reachable.
    survivors = [
        e for e in survivors
        if km_between(
            USER["home"],
            (e["places"][0]["mapPosition"]["coordinates"][1],
             e["places"][0]["mapPosition"]["coordinates"][0]),
        ) <= USER["max_km"]
    ]
    stages.append(("within reach", len(survivors)))

    total = stages[0][1]
    print(f"A {USER['age']}-year-old, {USER['balance_general']} RUB left "
          f"(cinema pool empty), free evenings and weekends,\n"
          f"willing to travel {USER['max_km']:.0f} km.\n")
    print(f"{'stage':<34}{'left':>7}{'% of all':>11}")
    print("-" * 52)
    for name, n in stages:
        print(f"{name:<34}{n:>7}{n / total:>10.0%}")
    print("-" * 52)
    print(f"\n{total} events -> {len(survivors)}. "
          f"Deterministic filters alone remove {1 - len(survivors) / total:.0%}.\n")

    # What is actually left, by archetype. This is the interesting part: if the
    # long tail does not survive the funnel, the product has nothing to offer.
    print("what survives, by archetype:")
    kinds = Counter(labels[e["_id"]]["archetype"] for e in survivors)
    for key, n in kinds.most_common():
        started = sum(1 for l in labels.values() if l["archetype"] == key)
        print(f"  {key:18s} {n:5d} of {started:5d}  ({n / started:.0%} survived)")

    # The count above is over the whole 3-month catalogue, which is not what a
    # user faces. What they actually face is "this Saturday evening". That is
    # the number the product has to get right.
    print()
    for probe in ("2026-10-03", "2026-10-10", "2026-10-17"):
        day_all = sum(
            1
            for e in events
            for s in e["places"][0]["seances"]
            if s["startLocal"].startswith(probe)
        )
        day_ok = sum(
            1
            for e in survivors
            for s in e["places"][0]["seances"]
            if s["startLocal"].startswith(probe)
            and is_free_time(datetime.fromisoformat(s["startLocal"]))
        )
        print(f"showtimes on {probe} (Sat):  {day_all:>4} listed  ->  {day_ok:>3} "
              f"worth showing this user")

    print("\nsample of what a ranker would then choose between:")
    for e in survivors[:8]:
        first = e["places"][0]["seances"][0]["startLocal"]
        print(f"  {e['price']:>5} RUB  {first}  {e['name'][:52]}")


if __name__ == "__main__":
    main()
