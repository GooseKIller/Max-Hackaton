---
Design note. Status: built and tested. Implementation:
[backend/app/timing.py](../../backend/app/timing.py)
---

# Time as a signal

Beyond like and dislike, we record **how long someone took to answer**.

A tap says *what* they chose. The delay says *how much they meant it*.

## Why this is worth doing

The implicit-feedback literature is consistent that dwell time correlates with
explicit ratings, and — more usefully — that it **dampens false positives** a click
alone would record at full strength. Clicks are noisy: clickbait, a title that does
not match the content, a mis-hit. Dwell time is the standard correction.

We cannot measure dwell. A chat bot sees no scrolling and no focus events. But in a
**one-card-at-a-time feed** the gap between our card arriving and their button coming
back *is* the time spent on that card — a closer proxy than dwell time on a web page,
where the clock keeps running on a tab nobody is looking at.

## The asymmetry, which is the actual insight

The obvious reading — "longer means more interested" — is wrong for a rejection.

| | Reading | Weight |
|---|---|---|
| **Fast no** (< ~4s) | Nothing held them. This is the judgement we want. | full |
| **Slow no** (4s–2min) | They read it, weighed it, and still said no. That is a no about *this event*, not about its kind. | **0.55** |
| **Fast yes** | The picture and title were enough. Confident. | full |
| **Slow yes** | A hesitant yes. | 0.8 |
| **Reflex** (< 1.2s) | Under a second nobody has read a venue name. A thumb, not a taste. | 0.6 |
| **Walked away** (> 2min) | The gap is about their life, not the card. Read nothing into it. | full |

The slow-no case is the one that matters. If someone spends eight seconds on an
immersive theatre card and then declines *this particular* show, recording a full
negative on `tag:immersivnyy` teaches the ranker to avoid the exact thing that held
their attention. Damping it keeps the topic alive while still respecting the answer.

Measured on the real pipeline:

```
pause   0.5s -> latency     500 ms, strongest negative -0.600   # reflex, damped
pause     2s -> latency    2000 ms, strongest negative -1.000   # confident no
pause     8s -> latency    8000 ms, strongest negative -0.550   # considered, damped
pause   600s -> latency  600000 ms, strongest negative -1.000   # walked away, ignored
```

The 2-minute abandon cap is not a detail. Without it, an overnight pause would score
as the most deliberate decision anyone ever made.

## Fatigue: position in the session

Later swipes in one sitting say less. After a while people stop choosing and start
clearing the deck. Weight decays: full for the first 10, 0.75 to 25, 0.5 after.

One bored evening must not overwrite a taste built over weeks.

## The third signal: when they actually use the bot

This is almost certainly the most valuable of the three, and it is the one the
product needs most.

Onboarding used to ask *"когда тебе удобно ходить?"* — a question that asks people to
predict their own schedule, which they are bad at. **When they open the bot is
evidence.** Someone swiping at 22:40 on a Tuesday is not free at 10:00 on a Tuesday,
whatever they ticked.

That matters here more than in most products, because our single biggest filter is
time: roughly a third of the Kazan catalogue happens on weekday mornings at schools
and libraries, and getting a user's availability wrong either buries good events or
surfaces ones they cannot attend.

`free_time_evidence()` buckets usage into weekday-daytime, weekday-evening and
weekend. It is implemented and tested.

**It does not yet drive anything**, deliberately. Using the bot at 23:00 does not
prove someone is free at 23:00 — they may be lying in bed planning a Saturday. The
honest use is to *offer* a correction when the evidence clearly disagrees with the
setting, not to silently overwrite what they told us. That is the next step, and it
needs real usage data to calibrate the threshold.

## Other time signals worth considering

Not built. Listed so the choice is deliberate rather than forgotten:

- **Lead time preference.** Do they pick things happening this week or next month?
  Someone who only ever likes next-weekend events should not be shown December.
- **Return gap.** Days between sessions: the honest retention metric, and the input
  to deciding when a reminder is welcome rather than nagging.
- **Time-to-first-swipe.** How long the first card takes tells us whether the
  opening screen works. A product metric more than a ranking signal.

## What is stored

`interactions.latency_ms`, alongside the existing signal, surface, position and mood.
Added by migration; older rows have NULL and are treated as "unknown", which changes
nothing.

As with everything in that table: nothing reads it historically yet, but it cannot be
reconstructed later, so it is recorded from the first day.

## Honest limits

- **We time the answer, not the attention.** A person can read a card, lock the
  phone, and come back. The abandon cap handles the obvious case; the rest is noise
  we accept.
- **Network and client delay are inside the measurement.** A slow connection looks
  like deliberation. At our thresholds this is small, but it is real.
- **The absolute thresholds are reasoned, not fitted.** 1.2s, 4s and 2 minutes come
  from how long it takes to read three short lines, not from our data. They now only
  apply as a cold start — see below.

## Relative beats absolute

Fixed thresholds assume everyone reads at the same speed. They do not, and judging
them absolutely mislabels both ends of the distribution **systematically, forever**:

- Someone who answers every card in about a second is not being thoughtless — that is
  simply their pace. Against a fixed 1.2s line, every signal they ever give is damped
  to 0.6.
- Someone whose normal pace is ten seconds is not deliberating over each card.
  Against a fixed 4s line, every rejection they make is damped to 0.55.

So once we have five of a person's own answers, **"fast" and "slow" mean fast and slow
for them**: the latency is divided by their own median, and the thresholds become
ratios (below 0.45× is a reflex, above 1.6× is considered). The generic numbers
remain only as the cold start.

The median, not the mean — one overnight pause would drag a mean into nonsense.

One thing stays absolute on purpose: **walking away**. A two-minute gap is someone
leaving the conversation, however slowly they normally read.

This is the same move as relative position encoding in a transformer, and for the same
reason: the model should see *how this compares to its neighbours*, not an absolute
coordinate whose meaning drifts between users. It also repairs the weakness admitted
above — hand-picked constants matter much less once the scale is per-person.

## Sources

- [Reweighting Clicks with Dwell Time in Recommendation](https://arxiv.org/pdf/2209.09000)
- [Denoising Implicit Feedback for Recommendation](https://arxiv.org/pdf/2006.04153)
- [Analysis of Short Dwell Time in Relation to User Interest in a News Application](https://arxiv.org/pdf/2012.13992)
- [Recommending based on Implicit Feedback (Jannach et al.)](https://web-ainf.aau.at/pub/jannach/files/BookChapter_Social_Information_Access_2018.pdf)
- Related: [ranking.md](ranking.md), [database.md](database.md)
