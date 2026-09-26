"""
Simulate users swiping, and measure whether the recommender actually learns.

THIS IS SYNTHETIC. No real person did any of this. The output database is for
demos and for measurement, never for claims about real behaviour.

Why this exists: we built taste vectors, timing signals and an exploration schedule,
and had no way to answer the only question that matters about any of it — does it
converge? A ranker that ignores taste still returns three plausible events, so
"looks fine" proves nothing.

Each simulated person has a hidden true taste. They swipe according to it, with
realistic noise and realistic answering times, and we check whether what we learn
approaches what they actually like.

    python3 data/generate_users.py              # measure
    python3 data/generate_users.py --write-db   # also populate data/demo.db
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.catalog import FixtureSource  # noqa: E402
from app.dialog import Dialog  # noqa: E402
from app.labeling import label_all  # noqa: E402
from app.taste import Ranker, cosine, event_vector  # noqa: E402

SEED = 20261029
START = datetime(2026, 10, 1, 19, 0)

# Each persona is a hidden truth the simulated user acts on and we never see.
# `pace_ms` is how fast they answer when the decision is easy — deliberately
# varied, because the whole point of the relative timing baseline is that people
# read at different speeds.
PERSONAS = {
    "makes things": {
        "loves": {"master-klass", "remeslo", "tehnologii", "nauka"},
        "hates": {"klassika", "drama"},
        "pace_ms": 1_100,
    },
    "classic theatre": {
        "loves": {"klassika", "drama", "literatura"},
        "hates": {"tehnologii", "intellektualnaya-igra"},
        "pace_ms": 6_500,
    },
    "contemporary": {
        "loves": {"sovremennoe-iskusstvo", "immersivnyy", "tanec", "fotografiya"},
        "hates": {"klassika"},
        "pace_ms": 2_400,
    },
    "music": {
        "loves": {"muzyka", "tatarskaya-kultura"},
        "hates": {"zhivopis"},
        "pace_ms": 3_000,
    },
    "curious about everything": {
        "loves": {"nauka", "istoriya", "etnografiya", "arhitektura"},
        "hates": set(),
        "pace_ms": 4_200,
    },
}

SWIPES = 25


def appeal(event, persona: dict) -> float:
    """How much this persona actually wants this event, in [0, 1]."""
    tags = set(event.tags)
    score = 0.5
    score += 0.35 * len(tags & persona["loves"])
    score -= 0.35 * len(tags & persona["hates"])
    return max(0.02, min(0.98, score))


def answer_latency(rng: random.Random, persona: dict, pull: float) -> float:
    """
    How long this person takes to answer, in seconds.

    Two effects worth modelling, because both are what the timing code claims to
    read: people have their own pace, and a genuinely close call takes longer than
    an obvious one.
    """
    base = persona["pace_ms"] / 1000.0
    uncertainty = 1.0 - abs(pull - 0.5) * 2.0       # 0 = obvious, 1 = a coin flip
    seconds = base * (0.7 + 1.6 * uncertainty) * rng.lognormvariate(0, 0.35)
    if rng.random() < 0.04:
        seconds += rng.uniform(180, 900)             # put the phone down
    return max(0.3, seconds)


def run_persona(
    name: str, persona: dict, source, ranker: Ranker, store=None, rng=None,
    swipes: int = SWIPES,
) -> dict:
    rng = rng or random.Random(SEED)
    dialog = Dialog(source, store)
    uid = f"sim_{name.replace(' ', '_')}"
    clock = START

    for message in ("/start", str(rng.choice([15, 16, 17, 18])), str(rng.randrange(800, 5000, 50))):
        dialog.handle(uid, message, clock)
        clock += timedelta(seconds=2)

    liked, shown = [], []
    for _ in range(swipes):
        session = dialog._session(uid)
        if not session.last_shown:
            break
        card = session.last_shown[0].event
        shown.append(card)

        pull = appeal(card, persona)
        says_yes = rng.random() < pull
        clock = (session.last_sent_at or clock) + timedelta(
            seconds=answer_latency(rng, persona, pull)
        )
        dialog.handle(uid, "❤️ пойду" if says_yes else "👎 не моё", clock)
        if says_yes:
            liked.append(card)

    # Did we learn what they actually like? Compare the learned vector against a
    # vector built from the persona's real preferences.
    learned = dialog._session(uid).taste.weights
    truth = {f"tag:{t}": 1.0 for t in persona["loves"]}
    for t in persona["hates"]:
        truth[f"tag:{t}"] = -1.0

    # Precision of the final feed: of the next ten the ranker would show, how many
    # does this persona actually want?
    session = dialog._session(uid)
    from app.filters import candidates

    pool = candidates(source.all_events(), session.profile, clock)
    top = ranker.recommend(pool, session.profile, session.taste, n=10, today=clock.date())
    precision = sum(appeal(s.event, persona) for s in top) / max(1, len(top))
    baseline = sum(appeal(e, persona) for e, _ in pool[:10]) / max(1, len(pool[:10]))

    # Taste fit alone always prefers zero variety, so reporting it alone hides the
    # trade the ranker is deliberately making. Measure both.
    def spread(items) -> float:
        tags = {t for e in items for t in e.tags}
        return len(tags) / max(1, len(items))

    variety = spread([s.event for s in top])
    baseline_variety = spread([e for e, _ in pool[:10]])

    return {
        "persona": name,
        "liked": len(liked),
        "shown": len(shown),
        "alignment": cosine(learned, truth),
        "precision_at_10": precision,
        "baseline_at_10": baseline,
        "variety": variety,
        "baseline_variety": baseline_variety,
        "latency_baseline": session.last_timing.baseline_ms if session.last_timing else None,
        "true_pace": persona["pace_ms"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write-db", action="store_true", help="populate data/demo.db")
    ap.add_argument("--swipes", type=int, default=SWIPES)
    args = ap.parse_args()

    swipes = args.swipes

    fixture = ROOT / "data" / "kazan_events.json"
    if not fixture.exists():
        print("Missing catalogue. Run: python3 data/generate_fixtures.py")
        return 1

    source = FixtureSource(fixture)
    events = source.all_events()
    ranker = Ranker(events, label_all(events))

    store = None
    if args.write_db:
        from app.db import Store

        db_path = ROOT / "data" / "demo.db"
        if db_path.exists():
            db_path.unlink()
        store = Store(db_path)

    print(f"{len(events)} events · {swipes} swipes per persona · synthetic people\n")
    header = (f"{'persona':<26}{'liked':>7}{'learned':>9}"
              f"{'fit':>7}{'(date)':>8}{'variety':>9}{'(date)':>8}")
    print(header)
    print("-" * len(header))

    rows = []
    for i, (name, persona) in enumerate(PERSONAS.items()):
        row = run_persona(name, persona, source, ranker, store,
                          random.Random(SEED + i), swipes=swipes)
        rows.append(row)
        lift = row["precision_at_10"] - row["baseline_at_10"]
        print(
            f"{row['persona']:<26}{row['liked']:>4}/{row['shown']:<3}"
            f"{row['alignment']:>8.2f}"
            f"{row['precision_at_10']:>7.0%}{row['baseline_at_10']:>8.0%}"
            f"{row['variety']:>9.1f}{row['baseline_variety']:>8.1f}"
        )

    print()
    mean_align = sum(r["alignment"] for r in rows) / len(rows)
    mean_lift = sum(r["precision_at_10"] - r["baseline_at_10"] for r in rows) / len(rows)
    print(f"mean alignment with hidden taste: {mean_align:+.2f}")
    mean_var = sum(r["variety"] for r in rows) / len(rows)
    mean_var_base = sum(r["baseline_variety"] for r in rows) / len(rows)
    print(f"mean taste fit vs chronological: {mean_lift:+.0%}")
    print(f"mean variety (tags per event): {mean_var:.1f} vs {mean_var_base:.1f} by date")
    if mean_align < 0.1:
        print("-> FAIL: the ranker is not learning what these people like.")

    print("\nlatency baselines learned, against each persona's true pace:")
    for r in rows:
        got = r["latency_baseline"]
        print(f"  {r['persona']:<26} true {r['true_pace']:>6} ms   learned "
              f"{got if got else '—':>6}")

    if store:
        print(f"\n{store.stats()}")
        store.close()
        print("demo.db written. Point DB_PATH at it to demo a populated bot.")

    print("\nSynthetic people, synthetic events. Not evidence about real users.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
