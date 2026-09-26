"""
Does the ranking actually do anything?

A ranker that has quietly stopped responding to taste still returns three plausible
events, so "it looks fine" is not evidence. This measures it against the baseline the
official listing uses — plain chronological order — on three questions:

  1. Does it surface the long tail, or just the mainstream?
  2. Does a user's taste change what they get?
  3. Are the three picks actually different from each other?

It uses data/kazan_events_labels.json as ground truth. That file exists only for
evaluation; nothing in the product reads it, and the real feed will not provide it.

    python3 backend/eval_ranking.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.catalog import FixtureSource  # noqa: E402
from app.filters import candidates  # noqa: E402
from app.labeling import label_all  # noqa: E402
from app.models import UserProfile  # noqa: E402
from app.taste import MOOD_TARGETS, Ranker, Taste, event_vector  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 9, 24, 12, 0)
TODAY = date(2026, 9, 24)

# What we would like a 16-year-old to end up with. `long_tail` is the whole point of
# the product; `school_group` and `kids` reaching a teenager is a failure.
GOOD = {"long_tail", "exhibition"}
BAD = {"school_group", "kids", "baby"}


def teen(**kw) -> UserProfile:
    base = dict(user_id="e", age=16, balance_general=3200, balance_cinema=2000)
    base.update(kw)
    return UserProfile(**base)


def main() -> int:
    path = ROOT / "data" / "kazan_events.json"
    labels_path = ROOT / "data" / "kazan_events_labels.json"
    if not path.exists() or not labels_path.exists():
        print("Missing fixtures. Run:  python3 data/generate_fixtures.py")
        return 1

    source = FixtureSource(path)
    events = source.all_events()
    truth = {
        l["_id"]: l["archetype"]
        for l in json.loads(labels_path.read_text(encoding="utf-8"))["labels"]
    }
    ranker = Ranker(events, label_all(events))

    user = teen()
    pool = candidates(events, user, NOW)
    print(f"catalogue {len(events)} events -> {len(pool)} pass the hard filters\n")

    # --- 1. baseline vs ranked -------------------------------------------
    print("=" * 66)
    print("1. Chronological baseline vs ranked  (top 10)")
    print("=" * 66)

    baseline = [e for e, _ in pool[:10]]
    ranked = [s.event for s in ranker.recommend(pool, user, Taste(), n=10, today=TODAY)]

    for name, picks in (("chronological", baseline), ("ranked", ranked)):
        kinds = Counter(truth.get(e.id, "?") for e in picks)
        good = sum(v for k, v in kinds.items() if k in GOOD)
        bad = sum(v for k, v in kinds.items() if k in BAD)
        print(f"\n  {name:<16} long-tail/exhibition {good}/10   unwanted {bad}/10")
        print(f"  {'':<16} {dict(kinds)}")

    # --- 2. does taste move the results? ---------------------------------
    print("\n" + "=" * 66)
    print("2. Do different tastes get different results?")
    print("=" * 66)

    personas: dict[str, list[str]] = {
        "likes workshops": ["master-klass", "nauka", "tehnologii"],
        "likes classics": ["klassika", "drama", "literatura"],
        "likes visual art": ["zhivopis", "sovremennoe-iskusstvo", "fotografiya"],
    }

    results: dict[str, list[str]] = {}
    for label, tags in personas.items():
        taste = Taste()
        for e in events:
            if any(t in e.tags for t in tags):
                taste.add(event_vector(e, None), "like")
        picks = ranker.recommend(pool, user, taste, n=3, today=TODAY)
        results[label] = [p.event.name for p in picks]
        print(f"\n  {label}")
        for p in picks:
            kind = truth.get(p.event.id, "?")
            print(f"    {p.score:.3f}  [{kind:<16}] {p.event.name[:48]}")

    overlap = set.intersection(*(set(v) for v in results.values()))
    print(f"\n  shared by all three personas: {len(overlap)}/3")
    if len(overlap) == 3:
        print("  -> FAIL: taste is being ignored, everyone gets the same list.")
    elif len(overlap) == 0:
        print("  -> taste clearly separates the personas.")

    # --- 3. mood ---------------------------------------------------------
    print("\n" + "=" * 66)
    print("3. Does mood change the results?")
    print("=" * 66)
    by_mood: dict[str, set[str]] = {}
    for mood in MOOD_TARGETS:
        taste = Taste()
        taste.set_mood(mood)
        picks = ranker.recommend(pool, user, taste, n=3, today=TODAY)
        by_mood[mood] = {p.event.name for p in picks}
        print(f"\n  {mood}")
        for p in picks:
            print(f"    [{truth.get(p.event.id, '?'):<16}] {p.event.name[:48]}")

    distinct = len({frozenset(v) for v in by_mood.values()})
    print(f"\n  distinct result sets across {len(by_mood)} moods: {distinct}")

    # --- 4. diversity ----------------------------------------------------
    print("\n" + "=" * 66)
    print("4. Are the three picks actually different from each other?")
    print("=" * 66)
    taste = Taste()
    taste.add(event_vector(events[0], None), "like")
    picks = ranker.recommend(pool, user, taste, n=3, today=TODAY)
    names = [p.event.name for p in picks]
    venues = {p.event.place.name for p in picks}
    cats = {p.event.category for p in picks}
    print(f"\n  distinct titles: {len(set(names))}/3")
    print(f"  distinct venues: {len(venues)}/3")
    print(f"  distinct categories: {len(cats)}/3")
    if len(set(names)) < 3:
        print("  -> FAIL: a duplicate title reached the user.")

    print("\nSynthetic data — these numbers describe the fixture, not Kazan.")
    print("Re-run against the real feed once a PRO.Культура.РФ key arrives.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
