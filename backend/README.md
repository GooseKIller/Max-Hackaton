# Backend

Steps 1-3 of the build plan in [../docs/design/ranking.md](../docs/design/ranking.md):
hard filters, affect labelling, content-based taste ranking with diversity, and an
onboarding quiz. No collaborative filtering and no model at request time — the
reasoning is in the design note.

## Run it

### In a terminal, without a MAX token

The dialog does not know what MAX is, so the whole conversation runs locally. This is
the fastest way to iterate on wording and filters.

```bash
python3 data/generate_fixtures.py   # once, if data/kazan_events.json is missing
python3 backend/console.py
```

### As a real MAX bot (long polling, no public HTTPS needed)

```bash
cp .env.example .env    # put MAX_BOT_TOKEN in it
python3 backend/runner.py
```

### As a service (webhook, for deployment)

```bash
docker compose up --build
```

Then `http://localhost:8000/health`, with the webhook at `POST /webhook` and the
generated OpenAPI document at `/openapi.json`.

### When a key arrives

Both keys are wired: drop the value into `.env` and nothing else changes.

```bash
# MAX bot token — resolves the four unverified behaviours in one pass
python3 backend/check_token.py
python3 backend/probe_max.py --wait 30
python3 backend/probe_max.py --chat <id>    # sending, keyboards, proactive
python3 backend/runner.py                   # the bot is live in MAX

# PRO.Культура.РФ key — switches the catalogue to the live feed automatically
python3 backend/probe_catalog.py --locales Татарстан   # find the locale id
python3 backend/probe_catalog.py --save                # real numbers + a saved snapshot
```

`probe_catalog.py` answers the four questions the ranking design is blocked on, and
prints the real funnel numbers that replace the synthetic ones on the evidence slide.

### Tests

```bash
python3 -m pytest backend/app/tests -q
```

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
| `check_token.py` | is the MAX token valid? (`GET /me`) |
| `probe_max.py` | resolve the four unverified MAX behaviours, including proactive sends |
| `probe_catalog.py` | pull the real feed, answer the open data questions, print the real funnel |
| `eval_ranking.py` | does the ranking beat chronological order? measures it |

Three deliberate boundaries:

1. **The dialog does not know about MAX.** Three transports drive the same logic, and
   we could iterate on the conversation before having a token.
2. **Nothing above `catalog.py` knows where events come from.** The fixture was
   generated in the real API's schema precisely so this swap is free.
3. **Card limits live only in `config.py`.** They are policy and policy moved twice
   this year. Never hardcode one anywhere else.

## Things that are deliberately not here yet

- **The tag co-occurrence graph.** Step 7 — needs users we do not have yet.
- **A dense user embedding.** `taste_weights` is already a sparse one. A learned
  dense vector needs the interaction log to fill up first — see
  [../docs/design/database.md](../docs/design/database.md).
- **Persistence.** Sessions are in memory and die with the process. Fine for a demo;
  one place to change when it is not.
- **The mini app.** Scope is still open — see the open items in the root README.
- **Any ML at runtime.** By design: see
  [../docs/compliance-check.md](../docs/compliance-check.md). Labelling and embedding
  run offline and ship as data, which keeps the Docker build under the 5-minute cap
  and removes an external dependency a judge cannot reproduce.

## Known limitations

- **The catalogue is synthetic.** Every event is generated and ticket links point at
  `example.invalid`. See [../data/README.md](../data/README.md).
- **The balance is user-reported.** There is no public API for the Pushkin Card
  balance, so we ask and label it as their number, not a verified one.
- **The MAX keyboard payload shape is unverified.** It is written from the docs but
  has not been tested against a live token. It is isolated in `max_client.py` for
  that reason.
- **Docker is untested on this machine** — Docker was not running when this was
  written. The build must be measured against the 5-minute cap before submission.
- **No location question yet**, so the distance filter is inactive in the default
  flow. `UserProfile.home` and the filter both work; the dialog just does not ask.
