"""
Taste vectors and ranking — step 2 of docs/design/ranking.md.

Deliberately not machine learning at request time, and deliberately not
collaborative filtering. The reasoning is in the design note: roughly 1.8 tickets per
cardholder per year, and every event is permanently cold because it happens once. A
user-item matrix would be empty.

What works instead is content-based scoring over features we already have — curated
tags from the API, the category, and the affect axes derived offline — driven by many
cheap signals instead of a few expensive ones.

Vectors are sparse dicts rather than arrays. At ~40 dimensions that is fast enough,
needs no numpy, and stays readable: you can print a user's taste and understand it,
which matters when explaining a recommendation to a jury or to a 16-year-old.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from math import sqrt

from .labeling import AFFECT_AXES, EventLabels
from .models import Event, Seance, UserProfile

Vector = dict[str, float]

# How much each kind of interaction moves the taste vector.
# A tap through to buy is the strongest thing we can observe — we never see the
# purchase itself, let alone the attendance.
SIGNAL_WEIGHTS = {
    "buy_click": 3.0,
    "save": 2.0,
    "like": 1.0,
    "open": 0.5,
    "dislike": -1.0,
    "skip": -0.35,
}

# Score weights, from the design note.
W_TASTE = 0.45
W_DISCOVERY = 0.20
W_BUDGET = 0.15
W_CONVENIENCE = 0.10
W_URGENCY = 0.10

# How much a candidate is penalised for resembling something already picked.
MMR_LAMBDA = 0.35

# --- exploration -> exploitation -------------------------------------------
#
# Start wide, narrow fast. The shape is TikTok's; the schedule is not, and the
# difference matters more than the similarity.
#
# TikTok can explore for two hundred videos because its goal is to keep you there.
# Ours is the opposite: a good session ends in a couple of minutes with a ticket
# tapped (see docs/design/anti-engagement.md). We get perhaps ten swipes before the
# person is gone — satisfied, ideally. So the exploration budget is roughly an order
# of magnitude smaller and the decay has to be correspondingly sharp.
#
# Half the exploration is gone after this many signals.
EXPLORE_HALF_LIFE = 6.0
# Extra weight handed to discovery when the user is completely cold.
EXPLORE_BONUS = 0.30
# How much of the taste weight is withheld while exploring. Not all of it: even one
# swipe says something, and ignoring it would feel broken.
EXPLORE_TASTE_DAMPING = 0.7
# Extra diversity pressure while exploring.
EXPLORE_MMR_BONUS = 0.30


def exploration_rate(signal_count: int) -> float:
    """
    1.0 when we know nothing, decaying toward 0 as signals arrive.

    Hyperbolic rather than exponential: it keeps a small, non-zero amount of
    exploration forever, which is what stops a taste vector collapsing into a
    single corner of the catalogue — the failure mode where a theatre kid is shown
    theatre and nothing else until they leave.
    """
    return 1.0 / (1.0 + max(0, signal_count) / EXPLORE_HALF_LIFE)


def event_vector(event: Event, labels: EventLabels | None = None) -> Vector:
    """
    Feature map for one event.

    Tags carry the most weight because they are *hand-curated by the organiser* —
    free supervision we would otherwise have to infer from text.
    """
    v: Vector = {}
    for tag in event.tags:
        if tag:
            v[f"tag:{tag}"] = 1.0
    v[f"cat:{event.category}"] = 0.8
    v[f"place:{event.place.category}"] = 0.4
    if labels:
        for axis in AFFECT_AXES:
            value = labels.affect.get(axis, 0.0)
            if value:
                v[f"affect:{axis}"] = value
    return v


def mood_match(vectors: list[Vector], mood: str) -> float:
    """
    Did we actually find what they asked for?

    Returns the average pull along the axes the mood cares about, in [-1, 1].
    Used to admit when the catalogue has nothing close instead of quietly serving
    the nearest thing — a dishonest match destroys trust faster than no match
    (docs/design/emotional-anchors.md, "what this does not solve").
    """
    targets = MOOD_TARGETS.get(mood)
    if not targets or not vectors:
        return 0.0
    scores = []
    for axis, want in targets.items():
        key = f"affect:{axis}"
        got = sum(v.get(key, 0.0) for v in vectors) / len(vectors)
        scores.append(got if want > 0 else -got)
    return sum(scores) / len(scores)


def cosine(a: Vector, b: Vector) -> float:
    """Cosine similarity over the shared keys. Returns 0 for an empty vector."""
    if not a or not b:
        return 0.0
    shared = a.keys() & b.keys()
    if not shared:
        return 0.0
    dot = sum(a[k] * b[k] for k in shared)
    na = sqrt(sum(x * x for x in a.values()))
    nb = sqrt(sum(x * x for x in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass
class Taste:
    """
    One person's accumulated taste.

    `weights` is the running vector. Signals decay: what someone liked two months ago
    says less than what they swiped on this evening. See emotional-anchors.md — an
    anchor has a lifetime of weeks, not forever.
    """

    weights: Vector = field(default_factory=dict)
    # Session-only pull from the current mood. Kept apart from `weights` and never
    # written to the database: "what I want tonight" must not become "who I am".
    mood_overlay: Vector = field(default_factory=dict)
    signal_count: int = 0

    def add(self, vector: Vector, signal: str, decay: float = 1.0) -> None:
        w = SIGNAL_WEIGHTS.get(signal, 0.0) * decay
        if w == 0.0:
            return
        for key, value in vector.items():
            self.weights[key] = self.weights.get(key, 0.0) + w * value
        self.signal_count += 1

    def set_mood(self, mood: str | None) -> None:
        """
        Set the session's mood as a pull on the affect axes.

        **Replaces, never accumulates.** An earlier version added the mood straight
        into `weights`, which is persisted — so picking "что-то необычное" four
        times pushed `affect:novelty` to 5.6 and permanently swamped everything the
        user had actually swiped on. Mood is situational and lives for one session,
        exactly as docs/design/emotional-anchors.md says; taste is durable. Keeping
        them in separate fields makes that impossible to get wrong again.

        Passing None clears it.
        """
        self.mood_overlay = {}
        if not mood:
            return
        for axis, value in MOOD_TARGETS.get(mood, {}).items():
            self.mood_overlay[f"affect:{axis}"] = value

    def effective(self) -> Vector:
        """Durable taste plus tonight's mood — what scoring actually compares against."""
        if not self.mood_overlay:
            return self.weights
        merged = dict(self.weights)
        for key, value in self.mood_overlay.items():
            merged[key] = merged.get(key, 0.0) + value
        return merged

    @property
    def is_cold(self) -> bool:
        return self.signal_count == 0 and not self.weights


# The mood row from docs/design/tone.md, rule 6 — plain labels, no slang.
MOOD_TARGETS: dict[str, dict[str, float]] = {
    "что-то сильное": {"intensity": 1.2, "valence": -0.6},
    "что-нибудь смешное": {"valence": 1.2, "intensity": -0.2},
    "что-то необычное": {"novelty": 1.4, "effort": 0.3},
    "красиво": {"prestige": 0.8, "intensity": 0.3},
    "пойти с кем-то": {"social": 1.3},
    "недолго, рядом": {"effort": -0.5, "intensity": -0.4},
}


def budget_fit(event: Event, user: UserProfile) -> float:
    """
    How well this price uses the money that is actually at risk.

    This is a ranking heuristic, not a separate wallet. All events draw on the total;
    cinema additionally has a remaining sub-limit. The planner checks aggregate costs.
    """
    pool = user.balance_cinema if event.is_cinema else user.balance_general
    if not pool or pool <= 0:
        return 0.0
    if event.price > pool:
        return 0.0
    share = event.price / pool
    # Peak around spending a third to a half of what is left: big enough to matter,
    # small enough to leave room for something else.
    return max(0.0, 1.0 - abs(share - 0.4) * 2.0)


def convenience(event: Event, seance: Seance, user: UserProfile) -> float:
    score = 0.5
    if user.home is not None:
        from .filters import km_between

        km = km_between(user.home, (event.place.lat, event.place.lon))
        score = max(0.0, 1.0 - km / max(user.max_km, 1.0))
    # A weekend slot is easier than a weekday evening for a school student.
    if seance.is_weekend:
        score = min(1.0, score + 0.15)
    return score


def urgency(user: UserProfile, today: date | None = None) -> float:
    """Rises as the year ends and while a lot is still unspent."""
    from .config import BALANCE_EXPIRES

    today = today or date.today()
    days = max(0, (date.fromisoformat(BALANCE_EXPIRES) - today).days)
    time_pressure = 1.0 - min(1.0, days / 120.0)
    unspent = 0.5
    if user.balance_general:
        from .config import CARD_RULES_2026

        unspent = min(1.0, user.balance_general / CARD_RULES_2026.total)
    return 0.5 * time_pressure + 0.5 * unspent


def rarity(vector: Vector, corpus_frequency: dict[str, int], total: int) -> float:
    """
    The long-tail boost.

    Without this, someone who likes theatre gets theatre forever and the product
    becomes exactly as boring as the thing it replaces. Rare features score higher,
    so the power plant tour can beat the fifth drama production.
    """
    if not vector or total <= 0:
        return 0.5
    scores = []
    for key in vector:
        if not key.startswith(("tag:", "cat:")):
            continue
        freq = corpus_frequency.get(key, 0)
        scores.append(1.0 - min(1.0, freq / total))
    if not scores:
        return 0.5
    return sum(scores) / len(scores)


@dataclass
class Scored:
    event: Event
    seance: Seance
    score: float
    parts: dict[str, float]
    vector: Vector

    def top_reason(self) -> str:
        """Which component drove this pick — used to explain it in plain words."""
        return max(self.parts.items(), key=lambda kv: kv[1])[0]


class Ranker:
    """
    Scores and diversifies candidates.

    Built once per catalogue: it precomputes each event's vector and the corpus
    frequencies the long-tail boost needs.
    """

    def __init__(self, events: list[Event], labels: dict[int, EventLabels]):
        self._labels = labels
        self._vectors: dict[int, Vector] = {
            e.id: event_vector(e, labels.get(e.id)) for e in events
        }
        self._freq: dict[str, int] = {}
        for vec in self._vectors.values():
            for key in vec:
                self._freq[key] = self._freq.get(key, 0) + 1
        self._total = max(1, len(events))

    def vector_for(self, event: Event) -> Vector:
        return self._vectors.get(event.id) or event_vector(event, self._labels.get(event.id))

    def score(
        self,
        candidates: list[tuple[Event, Seance]],
        user: UserProfile,
        taste: Taste,
        today: date | None = None,
    ) -> list[Scored]:
        u = urgency(user, today)
        # Anneal: wide while we know nothing, narrowing as the person tells us more.
        explore = exploration_rate(taste.signal_count)
        w_taste = W_TASTE * (1.0 - EXPLORE_TASTE_DAMPING * explore)
        w_discovery = W_DISCOVERY + EXPLORE_BONUS * explore

        out: list[Scored] = []
        for event, seance in candidates:
            vec = self.vector_for(event)
            match = max(0.0, cosine(taste.effective(), vec))
            # Explore where we are uncertain, not where we are confident.
            #
            # The long-tail bonus used to be unconditional, which quietly punished
            # anyone whose genuine taste is popular: simulated users who love
            # classic theatre scored 17% WORSE than plain date order, because the
            # catalogue is full of classic theatre and rarity pushed them away from
            # exactly what they wanted. Gating the bonus on how well we already
            # understand an item is the bandit principle, and it costs the long tail
            # nothing — a rare event the user has no opinion on still has a low
            # match and still gets the full boost.
            parts = {
                "taste": match * w_taste,
                "discovery": rarity(vec, self._freq, self._total)
                * w_discovery
                * (1.0 - min(1.0, match)),
                "budget": budget_fit(event, user) * W_BUDGET,
                "convenience": convenience(event, seance, user) * W_CONVENIENCE,
                "urgency": u * W_URGENCY,
            }
            out.append(
                Scored(
                    event=event,
                    seance=seance,
                    score=sum(parts.values()),
                    parts=parts,
                    vector=vec,
                )
            )
        out.sort(key=lambda s: s.score, reverse=True)
        return out

    def diversify(self, scored: list[Scored], n: int, explore: float = 0.0) -> list[Scored]:
        """
        Maximal marginal relevance.

        Three recommendations should not be three drama productions at the same
        theatre, even if those are the three highest scores.

        Titles are de-duplicated first. The same production runs many times and
        appears as several records, and showing one twice reads as a broken product
        far faster than a merely mediocre pick does.
        """
        # Forced variety is a cost paid by the user, so charge it while we are
        # still guessing and refund it once we understand them. Held flat, it takes
        # someone with a strong, consistent preference and hands them a third of a
        # feed they did not ask for, forever.
        lam = MMR_LAMBDA * (0.4 + 0.6 * explore) + EXPLORE_MMR_BONUS * explore
        picked: list[Scored] = []
        seen_titles: set[str] = set()
        pool = []
        for s in scored:
            key = s.event.name.strip().lower()
            if key in seen_titles:
                continue
            seen_titles.add(key)
            pool.append(s)
        while pool and len(picked) < n:
            best, best_value = None, float("-inf")
            for cand in pool:
                penalty = max(
                    (cosine(cand.vector, p.vector) for p in picked), default=0.0
                )
                value = cand.score - lam * penalty
                if value > best_value:
                    best, best_value = cand, value
            if best is None:
                break
            picked.append(best)
            pool.remove(best)
        return picked

    def recommend(
        self,
        candidates: list[tuple[Event, Seance]],
        user: UserProfile,
        taste: Taste,
        n: int = 3,
        today: date | None = None,
    ) -> list[Scored]:
        return self.diversify(
            self.score(candidates, user, taste, today),
            n,
            explore=exploration_rate(taste.signal_count),
        )


def quiz_cards(
    events: list[Event],
    ranker: Ranker,
    n: int = 6,
    now: datetime | None = None,
) -> list[Event]:
    """
    Pick cards for onboarding that span the feature space.

    The point is coverage, not quality: a card that tells us nothing new is a wasted
    question, and a teenager will not answer many. Greedily choose the event least
    similar to everything already chosen.
    """
    pool = [e for e in events if e.tags or e.category]
    if not pool:
        return []
    chosen: list[Event] = [pool[0]]
    while len(chosen) < n and len(chosen) < len(pool):
        best, best_dist = None, -1.0
        for cand in pool:
            if cand in chosen:
                continue
            v = ranker.vector_for(cand)
            dist = 1.0 - max(
                (cosine(v, ranker.vector_for(c)) for c in chosen), default=0.0
            )
            if dist > best_dist:
                best, best_dist = cand, dist
        if best is None:
            break
        chosen.append(best)
    return chosen
