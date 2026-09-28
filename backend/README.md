# Backend

Steps 1-3 of the build plan in [../docs/design/ranking.md](../docs/design/ranking.md):
hard filters, affect labelling, content-based taste ranking with diversity, and an
onboarding quiz. No collaborative filtering and no model at request time — the
reasoning is in the design note.

## Run it

### In a terminal, locally

The dialog does not know what MAX is, so the whole conversation runs locally. This is
the fastest way to iterate on wording and filters.

```bash
python3 data/generate_fixtures.py   # once, if data/kazan_events.json is missing
PROCULTURE_API_KEY='' DB_PATH=data/console-local.db python3 backend/console.py
```

### As a real MAX bot (long polling, no public HTTPS needed)

```bash
cp .env.example .env    # only if .env does not exist; fill private settings
python3 backend/runner.py
```

To run polling and the reminder worker together in Docker:

```bash
docker compose -f compose.polling.yaml up -d --build
```

This is a standalone configuration, not an overlay for the UI/API. Coordinate
the handover first; do not run a second receiver for the team's bot.

### As a service (local UI/API)

```bash
docker compose up --build
```

This starts UI/API, not polling; it does not register a webhook. The reminder
worker requires the separate `live` profile. Then `http://localhost:8000/health`,
with the webhook at `POST /webhook` and the
generated OpenAPI document at `/openapi.json`.

The same image serves the React budget planner at `http://localhost:8000/app/` and
`GET /api/planner/meta`, `POST /api/planner/plans`. These endpoints are stateless:
they do not load or modify bot profiles. The synthetic demo runs locally. See [frontend setup and limits](../frontend/README.md).

### Connection checks

Private settings are read from `.env` automatically. Run the MAX commands below
only for your own instance or an agreed handover; the team's bot already runs.
Do not run another polling process or use polling and webhook simultaneously.

```bash
# MAX connection checks
python3 backend/probe_max.py --wait 30
python3 backend/probe_max.py --chat <id>    # sending, keyboards, proactive
python3 backend/runner.py                   # the bot is live in MAX

# PRO.Культура.РФ key — switches the catalogue to the live feed automatically
python3 backend/probe_catalog.py --locales Татарстан   # find the locale id
python3 backend/probe_catalog.py --save                # real numbers + a saved snapshot
```

`probe_catalog.py` answers the four questions the ranking design is blocked on, and
prints the real catalogue funnel numbers.

### Tests

```bash
python3 -m pytest backend/app/tests -q
```

Docker polling checks run in CI with `backend/tests/compose.polling-test.yaml`.
They use an isolated HTTP substitute, a separate database and no external network.
They cover the dialog, restart, shared consent and reminder delivery to that substitute;
they do not replace testing in real MAX clients.

## How it fits together

```
 MAX  ──webhook──►  app/main.py    ─┐
                                    ├─►  app/dialog.py  ──►  app/filters.py
 MAX  ──polling──►  runner.py      ─┤         │                    │
                                    │         │                    │
 you  ──terminal─►  console.py     ─┘         ▼                    ▼
                                        app/models.py       app/catalog.py
                                                                   │
                                                          fixture / PRO.Культура.РФ
```

| Module | Responsibility |
|---|---|
| `app/config.py` | settings, and the **card rules as data** with source and as-of date |
| `app/models.py` | domain objects, mirroring the PRO.Культура.РФ schema |
| `app/catalog.py` | `EventSource` protocol; fixture now, real API later |
| `app/filters.py` | hard filters — age fit, audience, time, money, distance |
| `app/labeling.py` | offline affect labelling: six axes from a lexicon, with evidence |
| `app/taste.py` | taste vectors, scoring, long-tail boost, MMR diversity, quiz cards |
| `app/db.py` | SQLite store — profiles, taste, the interaction log, sessions, cache |
| `app/dialog.py` | the conversation; transport-agnostic |
| `app/max_client.py` | MAX Bot API: send, long poll, webhook subscription |
| `app/main.py` | FastAPI: `/health`, `/webhook` |
| `console.py` | run the dialog in a terminal |
| `runner.py` | run the bot against MAX by long polling |
| `probe_max.py` | resolve the four unverified MAX behaviours, including proactive sends |
| `probe_catalog.py` | pull the real feed, answer the open data questions, print the real funnel |
| `eval_ranking.py` | does the ranking beat chronological order? measures it |

Three deliberate boundaries:

1. **The dialog does not know about MAX.** Three transports drive the same logic, and
   we could iterate on the conversation before connecting it to MAX.
2. **Nothing above `catalog.py` knows where events come from.** The fixture was
   generated in the real API's schema precisely so this swap is free.
3. **Card limits live only in `config.py`.** They can change. Keep a source and review
   date with them; do not treat media reports about proposals as current rules.

## Things that are deliberately not here yet

- **The tag co-occurrence graph.** Step 7 — needs users we do not have yet.
- **A dense user embedding.** `taste_weights` is already a sparse one. A learned
  dense vector needs the interaction log to fill up first — see
  [../docs/design/database.md](../docs/design/database.md).
- **Any ML at runtime.** By design: see
  [../docs/compliance-check.md](../docs/compliance-check.md). Labelling and embedding
  run offline and ship as data, which keeps the Docker build under the 5-minute cap
  and removes an external dependency a judge cannot reproduce.

## Known limitations

- **The catalogue is synthetic.** Every event is generated and ticket links point at
  `example.invalid`. See [../data/README.md](../data/README.md).
- **The balance is user-reported.** There is no public API for the Pushkin Card
  balance, so we ask and label it as their number, not a verified one.
- **Final MAX validation is pending.** The team checked polling and the basic
  dialog on 26 September; the current version still needs mobile/web verification.
- **Tests checked on 28 September 2026** — all 179 pass locally. These tests do not
  verify real MAX delivery or availability.
- **No location question yet**, so the distance filter is inactive in the default
  flow. `UserProfile.home` and the filter both work; the dialog just does not ask.

## Budget plans in this branch

After onboarding, select `собрать план` or type `/plan`. The bot searches 2–3-event
combinations among the top 30 ranked distinct events, enforces the shared total and
remaining cinema allowance, and rejects overlapping slots (45-minute transfer buffer).
It returns up to three distinct alternatives, not necessarily three.

Unknown overall balance allows browsing without a funded plan. Unknown cinema
allowance excludes cinema. Prices are estimates from the catalogue, not reserved seats.
No balance is debited. Details, limitations and demo steps:
[budget-plans.md](../docs/design/budget-plans.md).

SQLite persists profiles and sessions when a Store is supplied by console/runner/API.
`balance_reported_at` now advances only on explicit total-balance input. Earlier
versions updated that column on every message; historical timestamps from those
versions must not be used as evidence of a fresh balance confirmation.

Scheduled reminders are implemented with opt-in, cancellation, delivery tracking
and retry in `app/reminders.py` and `app/reminder_worker.py`. They require a separate
worker; polling does not start it. Real MAX delivery still needs verification.

For a clean local environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python -m pytest backend/app/tests -q
PROCULTURE_API_KEY='' DB_PATH=data/console-local.db .venv/bin/python backend/console.py
```

`app/config.py` automatically reads the local `.env`; existing environment variables
take precedence. Run `.venv/bin/python backend/runner.py` only for your own instance
or an agreed handover. Docker Compose reads its configured env file itself.
