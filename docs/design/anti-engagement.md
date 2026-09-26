---
Design note. Status: a principle, and the constraint the rest of the design answers to.
---

# We are not trying to keep anyone here

Our loop looks like TikTok's: one card at a time, a picture, a binary choice, learn
from the swipe. It is worth stating loudly what it is **not**.

> **TikTok's goal is that you stay forever. Ours is to get you out as fast as
> possible — into a theatre.**

A session that ends after ninety seconds with a tapped ticket link is a **success**.
A session where someone swipes for twenty minutes is a **failure**, however good it
looks on an engagement dashboard. Time in our bot is not value delivered; it is
friction between a person and their evening.

This is not a slogan. Several decisions in this repository follow from it, and would
have gone the other way under an engagement goal.

## What it changes

### The exploration budget is roughly ten times smaller

A recommender learns by exploring, and exploration costs the user patience they pay
in time spent. TikTok can afford two hundred mediocre videos to map a taste, because
every one of those videos is also the product being consumed.

We get perhaps ten swipes. So exploration has to anneal **sharply**: half the
exploration budget is gone after six signals
([taste.py](../../backend/app/taste.py), `EXPLORE_HALF_LIFE`). An engagement product
would decay this over hundreds of interactions and be right to.

| Signals | Exploration | Taste weight | Discovery weight |
|---|---|---|---|
| 0 | 1.00 | 0.14 | 0.50 |
| 3 | 0.67 | 0.24 | 0.40 |
| 6 | 0.50 | 0.29 | 0.35 |
| 12 | 0.33 | 0.35 | 0.30 |
| 60 | 0.09 | 0.42 | 0.23 |

The decay is hyperbolic rather than exponential so a little exploration survives
forever — that is what stops a taste vector collapsing into one corner of the
catalogue and showing a theatre kid nothing but theatre.

### Onboarding was cut from eleven steps to three

Not because short onboarding converts better — though it does — but because every
question is time taken from the thing the person actually wanted. Eleven steps and
2332 characters before the first event was us spending their evening on ourselves.

### The reminder is a fact, not a hook

"На карте 3200 ₽. Сгорают 31 декабря — это 68 дней." No countdown animation, no
streak, no "ты не заходил три дня". An engagement product would build exactly those
([tone.md](tone.md), rule 5). We are trying to be needed rarely and be right when we
are.

### We hand the user to a competitor's checkout on purpose

The ticket goes through the official `saleLink`. We could proxy it, wrap it, keep
them inside and measure the click. We do not, and the `buy_click` signal is weaker
for it. Sitting between a teenager and the real ticket page to harvest a conversion
event is exactly the trade this principle exists to refuse.

### Success metrics have to be inverted

What we should be measuring, if we get real usage:

| Good | Bad |
|---|---|
| Swipes until the first ticket tap — **lower is better** | Session length |
| Sessions per month staying **low** while tickets stay high | Daily active users |
| Share of the balance actually spent by 31 December | Retention curves |
| People who return once a month, not once a day | Time in app |

If a slide ever shows "average session length: 18 minutes" as an achievement, this
document is the argument that it is a bug report.

## Why this is also the right thing to put in front of a jury

The product is aimed at 14–22 year olds, mostly 15–18, attached to a state cultural
programme. Building a variable-reward loop for minors and calling it success would
be a bad thing to do and a worse thing to defend.

"Мы измеряем, как быстро человек от нас уходит" is a defensible answer to a question
about engagement metrics. "DAU" is not, for this audience, from this programme.

It also happens to be the honest description of the job: nobody wants a Pushkin Card
app. They want a good Saturday.
