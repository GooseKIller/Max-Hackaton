"""
Time as a signal.

A tap tells us *what* someone chose. How long they took tells us *how much they
meant it* — and the literature on implicit feedback is consistent that dwell time
correlates with explicit ratings and, more usefully, dampens false positives that a
click alone would record at full strength.

We cannot measure dwell: a chat bot sees no scrolling and no focus events. What we
can measure is the gap between our card arriving and their button coming back. In a
one-card-at-a-time feed that gap *is* the time spent on the card, which makes it a
closer proxy than it would be on a web page.

Three things are derived here:

1. **Confidence** — how much a like or dislike should move the taste vector.
2. **Deliberation** — whether the card was considered or reflexed past, which is a
   different fact from the answer itself.
3. **When the person is actually free** — inferred from when they use the bot,
   which is evidence where our onboarding question was a guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# Below this, the tap came back faster than the card could be read. It is a reflex,
# a double-tap, or a mis-hit — real, but not considered.
REFLEX_MS = 1_200

# The window in which a decision looks deliberate: long enough to read the title,
# price, time and venue, short enough to still be one sitting.
CONSIDERED_MS = 4_000

# Past this the person put the phone down. The gap stops being about the card and
# starts being about their life, so we stop reading anything into it. Without this
# cap an overnight pause would look like the most deliberate decision ever made.
ABANDON_MS = 120_000


# How many of a person's own answers we need before we trust their pace over the
# generic thresholds.
BASELINE_MIN_SAMPLES = 5

# Relative thresholds, as a multiple of this person's own typical pace.
REFLEX_RATIO = 0.45
CONSIDERED_RATIO = 1.6


def baseline(latencies: list[int]) -> int | None:
    """
    This person's own typical answering pace: the median of their recent answers.

    Median, not mean — one overnight pause would drag a mean into nonsense.
    """
    usable = sorted(x for x in latencies if x is not None and 0 < x < ABANDON_MS)
    if len(usable) < BASELINE_MIN_SAMPLES:
        return None
    return usable[len(usable) // 2]


@dataclass(frozen=True)
class Timing:
    """
    What we know about how a single answer arrived.

    **Relative where we can be, absolute only as a fallback.** Fixed thresholds
    assume everyone reads at the same speed, and they do not: a person who answers
    every card in a second is not being reflexive, that is simply their pace, and
    someone who always takes ten seconds is not deliberating over every one. Judged
    absolutely, the first is dismissed at 0.6 weight forever and the second has
    every rejection damped — both systematically mislabelled.

    So once we have enough of a person's own answers, "fast" and "slow" mean fast
    and slow *for them*. The generic thresholds are only a cold start.
    """

    latency_ms: int | None
    position: int
    # This person's own median latency, when we have enough samples to know it.
    baseline_ms: int | None = None

    @property
    def ratio(self) -> float | None:
        """How this answer compares with this person's own pace."""
        if self.latency_ms is None or not self.baseline_ms:
            return None
        return self.latency_ms / self.baseline_ms

    @property
    def is_reflex(self) -> bool:
        if self.latency_ms is None:
            return False
        r = self.ratio
        if r is not None:
            return r < REFLEX_RATIO
        return self.latency_ms < REFLEX_MS

    @property
    def is_considered(self) -> bool:
        if self.latency_ms is None or self.is_abandoned:
            return False
        r = self.ratio
        if r is not None:
            return r >= CONSIDERED_RATIO
        return self.latency_ms >= CONSIDERED_MS

    @property
    def is_abandoned(self) -> bool:
        # Absolute by nature: walking away is walking away at any reading speed.
        return self.latency_ms is not None and self.latency_ms >= ABANDON_MS


def confidence(signal: str, timing: Timing) -> float:
    """
    A multiplier on how much this answer should move the taste vector.

    The asymmetry is the interesting part, and it is not obvious:

    - A **fast no** is a confident no. Nothing about the card held them, and that
      is exactly the judgement we want — full weight.
    - A **slow no** is a no about *this event*, not about its kind. They read it,
      they weighed it, something in it had pull. Recording that at full negative
      weight teaches the ranker to avoid the very things the person was drawn to.
      So it is damped.
    - A **fast yes** is a confident yes — the picture and the title were enough.
    - A **slow yes** is a hesitant yes, and worth slightly less.

    Reflex-speed answers of either kind are damped: under about a second nobody has
    read a venue name, so we are recording a thumb, not a preference.
    """
    if timing.latency_ms is None or timing.is_abandoned:
        return 1.0

    if timing.is_reflex:
        # Too fast to have read the card. Still a signal, just a weak one.
        return 0.6

    if signal in ("dislike", "skip"):
        # Considering something and still declining it is a soft no.
        return 0.55 if timing.is_considered else 1.0

    if signal in ("like", "buy_click", "save"):
        return 0.8 if timing.is_considered else 1.0

    return 1.0


def fatigue(position: int) -> float:
    """
    Later swipes in one sitting say less than earlier ones.

    After a while people stop choosing and start clearing the deck. Treating the
    thirtieth reflexive dislike as seriously as the first would let one bored
    evening overwrite a taste built over weeks.
    """
    if position <= 10:
        return 1.0
    if position <= 25:
        return 0.75
    return 0.5


def weight(signal: str, timing: Timing) -> float:
    return confidence(signal, timing) * fatigue(timing.position)


def free_time_evidence(moments: list[datetime]) -> dict[str, int]:
    """
    When this person actually uses the bot.

    Onboarding used to ask "when is it convenient for you to go?", and the answer
    is a guess people give about themselves. When they open the bot is evidence.
    Someone swiping at 22:40 on a Tuesday is not free at 10:00 on a Tuesday, no
    matter what they ticked.

    Returns counts by bucket so a caller can decide what is enough to act on. We do
    not overwrite what the user told us — they may be planning for a free week —
    but a clear disagreement is worth surfacing rather than silently ignoring.
    """
    buckets = {"weekday_daytime": 0, "weekday_evening": 0, "weekend": 0}
    for moment in moments:
        if moment.weekday() >= 5:
            buckets["weekend"] += 1
        elif moment.hour >= 16:
            buckets["weekday_evening"] += 1
        else:
            buckets["weekday_daytime"] += 1
    return buckets
