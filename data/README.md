# Data

## ⚠️ This catalogue is synthetic

`kazan_events.json` is **generated, not real**. No event in it happened, no price is
real, and every ticket link points at `example.invalid` and will not resolve.

The venue names *are* real Kazan institutions. They are used so the catalogue reads
plausibly to someone who knows the city — nothing more.

This must be stated in the README of the submitted solution and on the presentation
slides. The track brief requires it explicitly: if the MVP uses test, prepared or
simulated data instead of a real integration, we have to say so and describe what is
needed to make the integration real. The brief also warns against imitating an
integration, which is why the fake ticket links use a guaranteed-dead domain rather
than a plausible-looking one.

## Why synthetic

The PRO.Культура.РФ API key is issued "upon a partnership arrangement" — a human
process with an unknown lead time, and our deadline is a week out. Waiting is not a
plan. See [../docs/outreach/api-key-request.md](../docs/outreach/api-key-request.md)
for the request that went out anyway.

## What makes it useful anyway

The generator is not a random data dump. It reproduces the specific distribution we
measured on the live culture.ru listing for Kazan, because our product's claim is that
the official listing is badly *shaped*, not badly *stocked*. If the fixture were
uniformly random, our ranking would have nothing to fix and the demo would prove
nothing.

Current mix (1,166 events, ~3,300 showtimes, ~3 months):

| Archetype | Share | Why it's in there |
|---|---|---|
| `school_group` | 22% | weekday 09:00–15:00 at lyceums and libraries — organised groups, useless to a teenager choosing for themselves |
| `classic_theatre` | 19% | the mainstream that dominates the official listing |
| `kids` | 17% | puppet theatre and fairy tales, `0+`/`6+` |
| `classical_concert` | 14% | philharmonic programmes |
| `baby` | 8% | literal baby concerts, `0+` — the thing we found tagged "Для молодежи" on the real site |
| `long_tail` | 8% | industrial tours, immersive theatre, workshops, quizzes — the part that makes the product feel non-boring |
| `exhibition` | 7% | long-running, many showtimes each |
| `cinema` | 6% | separate budget pool, capped at 2,000 RUB |

## Schema

The output matches the **PRO.Культура.РФ API 2.5 `pushkinsCardEvents`** response, field
for field: `_id`, `name`, `ageRestriction`, `description`, `shortDescription`, `tags[]`,
`category`, `isFree`, `price`, `maxPrice`, `saleLink`, `image`, and `places[]` with
`seances[]`, full address, `mapPosition.coordinates` and `accessible[]`.

This is the whole point. When a key arrives, only the data-source adapter changes —
nothing above it. Keep it that way: everything upstream reads this shape and nothing
else.

Two additions that are **not** in the real API:

- `_synthetic: true` on the envelope and on every event. Deliberate: it should be
  impossible to mistake this for real data, including by accident, later, by someone
  who wasn't in this conversation.
- `kazan_events_labels.json` — the ground-truth archetype and target audience per
  event. This is the answer key for evaluating our audience classifier. The real feed
  will not give us this, so nothing in the product may read it; it is for measurement
  only.

## Files

| File | What |
|---|---|
| `generate_fixtures.py` | the generator; fixed seed, reproducible |
| `kazan_events.json` | the catalogue (regenerate, don't hand-edit) |
| `kazan_events_labels.json` | ground-truth labels, for evaluation only |
| `check_funnel.py` | runs the hard-filter funnel over the catalogue and reports what survives |

```bash
python3 data/generate_fixtures.py && python3 data/check_funnel.py
```

## What the funnel currently shows

For a 16-year-old with 3,200 RUB left outside the cinema pool, free evenings and
weekends, willing to travel 8 km:

```
everything in the catalogue         1166   100%
legal age allows them in            1166   100%   <- removes nothing
not aimed at small children          837    72%
happens when they are free           615    53%
fits the remaining balance           549    47%
within reach                         543    47%
```

Two things worth reading carefully.

**The legal age filter removes literally nothing.** Every `0+`, `6+`, `12+` and `16+`
event passes for a 16-year-old, because `ageRestriction` is a legal minimum, not a
target audience. This is the cleanest possible demonstration of why the official
listing shows baby concerts to teenagers — and why a naive implementation of our
product would do exactly the same thing.

**Filters remove about half, not most.** An earlier estimate of ~70% was too
optimistic. All 220 classic theatre productions survive, and they should — they are
legitimately eligible. Culling the unreachable is the filters' job; choosing between
543 legitimate options is the ranker's job, and that is where the long-tail boost
earns its place.

The number closer to lived experience is per-evening: on a given Saturday the
catalogue lists ~65–70 showtimes, of which ~32–40 are worth showing this particular
user. Still too many to read, few enough to rank well.

## When the real key arrives

1. Write the API adapter against the same shape.
2. Re-run `check_funnel.py` against the real feed and **replace every number above**,
   including in the presentation.
3. Check the things synthetic data cannot tell us, listed as open questions in
   [../docs/design/ranking.md](../docs/design/ranking.md): how reliably
   `ageRestriction` is populated in practice, how many distinct tags the real feed
   uses, whether ticket availability is exposed.
4. Keep the fixture. It stays useful for tests, for offline development, and for
   demoing when the network is against us.
