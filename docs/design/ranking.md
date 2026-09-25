# How we rank events

Design note. Updated 25 September: filters, sparse vectors, a five-card chat quiz,
heuristic ranking and MMR are implemented. Budget plans are in `app/plans.py`.
Mini-app swipes, dense embeddings and tag co-occurrence remain proposals.
See [validation](../research/validation.md) and [budget contract](budget-plans.md).
Weights below are engineering defaults, not empirically optimised parameters.

The question this answers: *how do we pick 3 events out of ~1,100 that a specific
teenager will actually want, when we barely have any data about them?*

---

## 1. Why the TikTok algorithm does not transfer

The instinct — "people with similar tastes like similar things" — is collaborative
filtering. It is the right instinct and the wrong tool for this problem. Three reasons,
in order of how badly they hurt.

### Reason 1: the MVP has no interaction history to train on

The earlier 7.3m cards / 13m tickets calculation is not supported by its linked
source, and a universal “20 interactions” threshold was not established. Our
practical reason is sufficient: no historical user-item dataset is available to
this MVP. Start with content features and explicit feedback, then compare alternatives
when representative interactions exist. Purchases and UI interactions differ.

### Reason 2: our inventory is perishable

A TikTok video can be recommended a million times over two years, so its embedding
gets better and better as people interact with it.

A specific screening of «Кара Карамазовых» on 27 September happens **once** and then
ceases to exist. By the time an event has accumulated enough interactions to be
understood, it may be over. This makes showtime-ID collaborative filtering difficult
at launch; recurring productions, venues and tags may provide longer-lived signals.

### Reason 3: we cannot see the conversion

Tickets are bought outside our product, on the official `saleLink`. We can see that a
user tapped "buy", but not that they bought, and certainly not that they went and
enjoyed it. Our strongest signal is truncated.

**Conclusion:** no user-user or item-item collaborative filtering in the MVP. It is not
a matter of tuning — there is no data to tune on.

---

## 2. What we take from TikTok instead

The user's instinct is still right; it just points at the interface, not the algorithm.
What actually makes TikTok's loop work is not the matrix factorisation — it is that
**it collects a huge number of cheap signals very quickly, and reacts to them inside the
same session.**

We can copy that exactly. The fix is to **change what we count.**

Record explicit micro-interactions, with their limitations:

| Signal | Weight | How often we get it |
|---|---|---|
| Tapped through to buy | +3.0 | rare, strongest |
| Saved / added to plan | +2.0 | occasional |
| Swiped right / "интересно" | +1.0 | **constant** |
| Opened the detail card | +0.5 | constant |
| Swiped left / "не моё" | −1.0 | **constant** |
| Shown and skipped 3+ times | −0.5 | constant |

**One onboarding session of swiping through 20 event cards gives us ten times more
signal than a year of ticket purchases.** That is the whole answer to "will we have
enough data": yes, if we ask for the right data.

This also decides a product question for us: swiping through cards is a catalogue
interaction with many items on screen and repeated visits, which per the MAX brief's own
rule belongs in a **mini app**, not in chat.

---

## 3. The actual ranking pipeline

Four stages. Most of the value is in the first one, which contains no machine learning
at all.

### Stage A — Hard filters (eliminate, don't rank)

```
candidates = events where
    status == "accepted"
    and seance.start  >  now + lead_time
    and seance.start  in  user.free_windows        # evenings, weekends
    and event.ageRestriction <= user.age
    and audience_fit(event, user.age) >= threshold # NOT a baby concert
    and event.price <= remaining_pool(event.category)
    and travel_time(user.home, place.coordinates) <= user.max_travel
```

This is where the "boring events" problem is actually solved. Our measurements on the
Kazan listing suggest ~1,100 events collapse to somewhere around a hundred once you
require the right age band and a time when a school student is not in class.

**`audience_fit` is the interesting piece here.** `ageRestriction` is a *legal minimum*,
not a target audience — a baby concert is `0+`, and `0 <= 16`, so a naive filter keeps
it. That is exactly the bug we found on the official site, where «Беби-концерт» appears
under the "Для молодежи" filter.

So we compute a separate target-audience label offline, once per event, from:
- `ageRestriction` combined with `category` and `placeCategory`
  (`0+` + `спектакли` + `театр кукол` → small children)
- title and description keywords (`бэби`, `беби`, `для малышей`, `утренник`, `сказка`)
- the organising institution's type (a lyceum at 10:00 on a Tuesday → organised school group)

Rules first, LLM-assisted labelling for the ambiguous remainder. This is cheap, runs
offline, and directly fixes a failure the official product demonstrably has — which
makes it a strong demo moment.

### Stage B — Score the survivors

```
score =  0.45 * taste
       + 0.20 * discovery
       + 0.15 * budget_fit
       + 0.10 * convenience
       + 0.10 * urgency
```

**`taste`** — cosine similarity between the user vector and the event vector.

An event vector is the blend of three things, all of which we get from the API for free:
- its **tags** (the API returns curated tag ids and names — this is hand-labelled
  metadata we do not have to infer)
- its **category** and organisation/place category
- a **text embedding** of `name + shortDescription`

The user vector is:

```
user_vector = normalise(
      w_quiz * quiz_vector
    + Σ  decay(age_of_signal) * weight(signal) * event_vector(signal.event)
)
```

**`discovery`** — an explicit long-tail boost, inverse to how heavily an event is already
promoted elsewhere. Without this term a theatre kid gets more theatre forever, and the
product becomes exactly as boring as the thing it replaces. This term is what surfaces
the power plant tour.

**`budget_fit`** — a price-share heuristic. The planner checks the aggregate total
and remaining cinema sub-limit; these are not independent wallets. Minimum leftover
is one optional plan mode, not a substitute for relevance.

**`convenience`** — travel time and time-of-day fit.

**`urgency`** — rises as 31 December approaches and as the unspent balance stays large.

### Stage C — Diversify

Take the top N by score, then apply maximal marginal relevance: each next pick is
penalised for similarity to what is already picked. Three recommendations should not be
three drama productions at the same theatre.

Roughly one slot in three or four is a deliberate **wildcard** from a category the user
has not explored. This is epsilon-greedy exploration, and it doubles as our only way to
learn what a user likes outside their stated interests.

### Stage D — Explain

Every recommendation carries one sentence saying *why*: "ты отметил иммерсивный театр —
здесь похожая механика, но про энергетику". 

This is not decoration. The brief requires us to separate facts, calculations and
recommendations so the user understands where a result came from. An explained
recommendation is also far more persuasive to a 16-year-old than a bare list, and it is
a visible product surface for the jury.

An LLM is a good fit for writing these sentences and for the offline audience labelling.
It is **not** allowed anywhere near the card rules — limits, sub-limits and eligibility
come from configuration with a source link and an as-of date, per the brief's warning
about presenting a model's guess as an official fact.

---

## 4. Cold start

**A brand-new user, zero history.** A 60-second onboarding: swipe through ~20 cards
chosen to span the tag space. That produces a usable taste vector immediately. Combined
with age, city and free-time windows from the chat onboarding, the first
recommendation is already personal. This is why the demo works for user number one —
which matters, because at judging time every user is user number one.

**A brand-new event, zero history.** Content-based scoring handles this natively: a new
event gets a vector from its text and tags the moment it appears in the API feed. No
warm-up period. For perishable inventory this is not a workaround, it is the correct
design.

---

## 5. Where collaborative filtering *can* work: on tags, not events

There is one place the user's original instinct fits, and it is worth building because
it is cheap.

Do co-occurrence on **tags**, not on event IDs. "People who liked `иммерсивный` also
liked `современный танец`" is a statement about ~200–300 tags, not about 1,100
one-off events — and unlike events, tags persist across seasons and across cities.

That makes the matrix small enough to learn something from a few hundred users, and it
keeps its value when the entire catalogue turns over. It is also the natural upgrade
path: log every signal from day one, and when we have enough users the tag graph starts
contributing without any redesign.

This is worth saying explicitly in the presentation, because **scaling is 35% of the
product score**. The ranking core, the signal schema and the tag graph are the part that
stays the same in a new city; only the event feed and the regional tag vocabulary change.

---

## 6. Implementation notes

**Embeddings.** `cointegrated/rubert-tiny2` — 29.4M parameters, ~111 MB, 312-dimensional,
Russian-native, very fast. `intfloat/multilingual-e5-small` (384-dim) is stronger but
heavier.

The Docker build must finish in **under 5 minutes**, so do not download a model during
build. Two safe options: precompute event embeddings offline and ship the vectors, or
bake a small model into the image deliberately. Decide when we measure the build.

For the first working version, TF-IDF over tags plus category one-hot is very likely
good enough and has zero model weight. Add embeddings only when we can show they improve
something.

**What we log from day one** (this is what makes everything above possible later):
every impression, every swipe, every detail open, every buy tap — with the event id,
its tags, the position in the list, and a timestamp. Cheap to store, impossible to
reconstruct after the fact.

---

## 7. What to build first

In order. Each step is demoable on its own.

1. **Hard filters only.** Age fit, time fit, budget fit, distance. No scoring at all.
   This alone turns 1,100 events into a usable shortlist and fixes the baby-concert bug.
2. **Quiz + content-based taste.** Tags and categories, cosine similarity.
3. **Swipe feedback loop** in the mini app, updating the vector live.
4. **Diversity and the wildcard slot.**
5. **Budget planning** — fit a set to the total balance and remaining cinema allowance.
6. **Explanations.**
7. *Later, not for the MVP:* the tag co-occurrence graph.

## Open questions

- [ ] How reliably is `ageRestriction` populated in the real feed? If most events are
      `0+` by default, the audience classifier carries the whole load.
- [ ] How many distinct tags does the Kazan feed actually use? This sizes the whole
      tag-vector approach.
- [ ] Do we have any popularity signal at all from the API, or is `discovery` purely
      inverse-frequency within our own catalogue?
- [ ] Does the API expose remaining ticket availability? Recommending a sold-out event
      is the fastest way to lose a user's trust.

All four need the API key to answer.

## Sources

- [Regional VTB reporting via Sib.fm; does not support the withdrawn 7.3m/13m claim](https://sib.fm/news/2026/07/27/vtb-naibolee-aktivno-pushkinskuyu-kartu-oformlyayut-starsheklassniki)
- [cointegrated/rubert-tiny2](https://huggingface.co/cointegrated/rubert-tiny2)
- [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small)
- Evidence for the filtering problem: [hypothesis-boring-events.md](../research/hypothesis-boring-events.md)
