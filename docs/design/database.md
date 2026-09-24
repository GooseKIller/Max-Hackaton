---
Design note. Status: built. Schema version 1.
Implementation: [backend/app/db.py](../../backend/app/db.py)
---

# The database

## Why it exists

Until now a taste vector died with the process. Every conversation started cold, and
every swipe a user gave us was thrown away — including the swipes that make any
future model possible.

## Why SQLite

Deliberate, not lazy:

- **No extra container.** `docker compose up` stays one service and the build stays
  far inside the brief's 5-minute cap.
- **No new dependency** to pin — it is in the standard library.
- **A single file a judge can open.**

The schema is written in SQL that Postgres also accepts, and everything goes through
one `Store` class. Moving to Postgres for a real pilot touches that file and nothing
else. That is the honest answer to "how does this scale": for one city it does not
need to yet, and the path is one file wide.

## About user embeddings

The instinct is right, with one correction worth making explicitly.

**We already have a user embedding.** `taste_weights` is it — a sparse vector over
features like `tag:immersivnyy`, `cat:kino`, `affect:novelty`. It is a real embedding;
it is just interpretable rather than dense. You can read it:

```
affect:novelty  +2.3
tag:fotografiya +1.0
tag:istoriya    +1.0
```

That readability is a feature, not a limitation. When a jury asks why an event was
recommended, "this person's strongest signal is novelty, and this event scores high on
novelty" is an answer. A 128-dimensional float array is not.

**A dense learned embedding is a different thing, and we cannot train one yet.**
It would have to be learned from something, and the honest options are:

| Source | Verdict |
|---|---|
| Collaborative signal (users who liked X also liked Y) | Needs users we do not have. ~1.8 tickets per cardholder per year. |
| Average of liked events' text embeddings | Possible, but carries the same information as `taste_weights` with less interpretability. |
| A model trained on our own interaction log | **The real path — and it needs the log to exist first.** |

So `user_embeddings` is in the schema, empty, with a `model` column so vectors from
different models never get mixed. Filling it today would be cargo cult. Filling it in
three months, from `interactions`, is a plan.

**This is why `interactions` is the strategically important table.** Nothing reads it
yet. It is written anyway, because a log can be replayed into any future model and
cannot be reconstructed after the fact.

## Schema

```
users              one row per person — age, balance, free time, anchor
taste_weights      the sparse taste vector: (user_id, feature) -> weight
user_embeddings    room for a dense vector later; empty today
interactions       every signal, ever. the training data for anything future
sessions           conversation state, so a restart does not drop someone
events             catalogue cache, in raw API shape
event_labels       derived affect labels, keyed by which labeller produced them
schema_meta        version
```

### `users`

No names, no contact details. The MAX user id is enough to hold a conversation, and
anything more is data we would have to protect without needing it.

`balance_general` / `balance_cinema` are **user-reported** — there is no public API
for the Pushkin Card balance — and stored with `balance_reported_at` so we know how
stale the figure is. Never presented as verified.

`anchor` and `anchor_set_at`: "what got you recently", per
[emotional-anchors.md](emotional-anchors.md). It has a lifetime of weeks, hence the
timestamp; a stale anchor should decay rather than steer someone forever.

`home_lat` / `home_lon` are optional and coarse, used only to compute a distance.

### `taste_weights`

One row per feature. Written on every turn, read when a session is rehydrated.
`top_features()` exists so a human can read someone's taste in plain words.

### `interactions`

```
signal   impression | open | like | dislike | skip | save | buy_click
surface  quiz | feed | reminder
position rank in the list it was shown in
mood     the session's mood at the time
```

`position` matters: an event clicked from rank 3 is a stronger signal than the same
event clicked from rank 1, and without the position we cannot tell them apart later.

`buy_click` is the strongest thing we will ever observe. We do not see the purchase
— it happens on the external `saleLink` — and we certainly never see attendance. Any
claim we make about what people attend has to be labelled as a proxy.

### `event_labels`

Keyed by `(event_id, labeler)` so upgrading from `rules-v1` to an LLM pass adds rows
rather than silently overwriting, and the two can be compared. `why` stores the
evidence behind each score, so any recommendation can be audited back to the words
that produced it.

## Data about teenagers

The audience is 14-22 and mostly 15-18. Decisions that follow from that:

- Store the MAX user id, never a name or contact details.
- Home location is optional, coarse, and only ever used for a distance.
- `forget(user_id)` deletes everything about one person in one call, so a deletion
  request cannot half-miss a table.
- The interaction log is behavioural, not content: which event, which signal, when.
  It holds nothing a person typed in free text.

The `anchor` field is the one exception — it is free text the user typed. It is a
title of a film or book, but it is still their words, and it is covered by `forget()`.

## Operations

```bash
python3 backend/console.py     # creates data/app.db on first run
```

`GET /health` reports row counts. The file is gitignored — it holds real user data
once the bot is live, and the brief forbids committing anything of the sort.

There are no migrations beyond `CREATE TABLE IF NOT EXISTS` at schema version 1. When
the schema changes before the deadline, the honest move is to delete the file and
start again rather than build a migration system we will use once.

## What is not stored yet

- **Which recommendations turned into a tap on the ticket link** beyond the
  `buy_click` signal — no outbound click tracking, deliberately: it would mean
  proxying the official purchase link, and we do not want to sit between a user and
  the real ticket page.
- **Anything about the mini app**, which does not exist yet.
- **Aggregates.** Counts are computed on the fly. At this size that is correct; a
  materialised view is a problem for a scale we do not have.
