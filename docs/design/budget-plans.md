# Budget plans: implemented contract

Status: implemented in this contribution, 25 September 2026. Entry point:
`Dialog.handle(user_id, "собрать план", now)` after onboarding; domain function:
`build_plans(ranked, profile)` in `backend/app/plans.py`.

## Inputs and output

- Reuse existing `Scored` events/seances, user profile and interest score. The caller
  applies the existing age, time, price and optional distance filters first.
- `balance_general` retains its database name for compatibility: it means **total
  remaining balance**, not a non-cinema wallet. `balance_cinema` is the reported
  remaining allowance within it; `None` means unknown/excluded, zero means exhausted.
- `Plan` contains `kind`, `items`, `total`, `cinema_total`, `remaining`. No payment state.
- Up to three distinct event sets: `interests` (mean relevance first), `variety`
  (category diversity first), `budget` (minimum remainder among remaining feasible
  sets). If modes yield the same set, don't repeat it under another heading.

## Search and limitations

Enumerate pairs/triples from at most 30 distinct ranked events (at most 4,495
combinations). This is a bounded shortlist search, not a global optimum. Each event
uses its first suitable seance selected upstream; alternate showtimes are not searched.

Check aggregate total, aggregate cinema, unique event IDs/production-name+venue pairs, positive duration,
non-overlapping intervals plus a fixed 45-minute transfer buffer. Current-year plans
end by `BALANCE_EXPIRES`; this is a product planning horizon, not a rule prohibiting
the purchase of tickets for later performances. Travel routes and ticket stock are
not verified. Do not label this “one outing” or promise reliable travel times.

The search works with catalogue minimum prices. For variable prices the UI says
“от” and labels the calculated remainder as an upper bound. Every plan asks the user
to check seller price and availability. No automatic debit and no inferred purchase.

`balance_reported_at` is persisted on explicit total input, not every interaction.
SQLite already has that column; no destructive migration is needed. Earlier versions
did not preserve this meaning, so request a fresh balance from returning pilot users.

## Reproducible demo

From repository root after installing dependencies:

```bash
.venv/bin/python backend/console.py
```

Use `заново` if a console profile already exists. Answer age `16`, total `3000`, cinema
`без кино`, free time `вечером и в выходные`, mood `что-то необычное`, then answer or
skip the five quiz cards. Select `собрать план`. Expected: distinct plans where the
catalogue permits them, totals no greater than 3,000, no cinema, explicit synthetic
data warning. If the fixture dates are past, use the fixed-date automated tests;
do not relabel stale fixture dates as current real events.

Additional checks: `другой остаток` → `1500` → `0` updates the budget without
repeating the quiz; negative/range input is rejected; `не знаю` permits browsing
without inventing money; restart with the same SQLite file preserves the report date.

```bash
.venv/bin/python -m pytest backend/app/tests -q
```

## Future mini-app seam

The domain function is independent of MAX and can back a future authenticated HTTP
endpoint. Do not expose profiles based only on a query-string user ID. Validate MAX
`initData` server-side and derive identity before reading the profile. Frontend can
render structured Plan data and instrument explicit selections; this branch does not
pretend that endpoint, bridge validation or UI already exists.
