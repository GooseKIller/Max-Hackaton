# Development audit and contribution plan

Reviewed 25 September 2026 against upstream `443c187` (24 September), then the local
contribution branch `feat/budget-plans-and-product-research`.
This is a source review and local test result, not certification of a deployed bot.

## What the team already has

| Area | Evidence in upstream | Assessment |
|---|---|---|
| Python bot | `backend/app/dialog.py`, `console.py`, `runner.py` | Age/balance/time/mood questions, five-card quiz, recommendations and commands |
| Recommendation engine | `filters.py`, `taste.py`, `labeling.py` | Rules, sparse vectors, feedback, scoring, diversity; useful base to extend |
| Persistence | `db.py`, SQLite tables and tests | Profiles, taste, interactions and session state survive process restart |
| MAX adapter | `max_client.py`, `main.py`, probe scripts | REST/polling/webhook code exists; live integration not established by this review |
| Catalogue | `catalog.py`, generated JSON and labels | Reproducible synthetic data; ProCulture adapter needs key and real-feed verification |
| Packaging | Dockerfile, Compose, pinned top-level requirements | Image builds locally; exact transitive versions are not locked |
| Research | `docs/research`, `docs/design` | Substantial design work, but several inferences and implementation-status claims needed correction |

No React/MAX UI application, authenticated mini-app endpoints, scheduled reminder
worker, purchase integration or measured user study exists in the inspected tree.
This paragraph describes **upstream**, not the later contribution: our branch now
includes the standalone React planner and stateless API described below.
The `balance` command is not a proactive reminder. A source adapter is not a live
integration until access, parsing and data quality are tested.

## Delivered in this contribution

1. **Budget semantics:** total and cinema remaining allowance are asked separately;
   unknown total remains unknown, unknown cinema excludes cinema. Cinema must fit
   the shared total as well as the sub-limit. Reject negative/range/mixed-number input.
2. **Plans:** existing filtered/ranked candidates produce distinct 2–3-event
   alternatives with aggregate budgets, duration/overlap checks, transfer buffer,
   price-range caveats, bounded search and a reachable chat action. No new ML service.
3. **Honest feedback:** persist the actual balance-report timestamp, remove fabricated
   buy clicks from typed event names, omit dead synthetic purchase links, and avoid
   promising proximity when no home location was supplied.
4. **Reproducibility:** service startup tests, dialog/plan regressions, a persistent
   Compose volume for SQLite and optional `.env` for token-free local startup.
5. **Research and copy:** reviewed `takes.md`, evidence register, interview questions,
   controlled task protocol, metric definitions, budget contract and source-note
   corrections. No invented interview outcomes or real-catalogue quality percentages.
6. **Planner interface:** React/TypeScript at `/app/`, grouped settings-style inputs,
   bottom sheets for interests/time, plan details, individual-event fallback,
   light/dark styles and strict stateless Python API. Same-origin Docker build.
   No read/write access to the bot's profiles, no invented authentication or purchase
   analytics. [Setup and tests](../frontend/README.md), [copy](design/planner-copy.md).

## Best next work packages

Suggested ownership, to coordinate with the team before parallel edits:

| Priority | Package | Suggested owner | Done when |
|---|---|---|---|
| P0 | MAX integration hardening | Backend owner | Bot-start update handled; callbacks acknowledged; webhook secret validated; duplicate updates do not repeat actions; malformed updates cannot crash polling; verified in MAX mobile and web |
| P0 | Real pilot catalogue | Research/data owner | Checked source snapshot or working API key; Kazan filter confirmed; live prices, availability links and durations reviewed; source/retrieval time retained |
| P1 | MAX integration of the delivered planner UI | Frontend/backend owners | Register HTTPS app URL; validate initData before optional profile sync; verify mobile/web launch/back/links; add explicit selection/click instrumentation |
| P1 | Reminder delivery | Us/backend after contract agreement | Explicit opt-in and opt-out, Moscow-time schedule, dated reported balance, per-user/year/rule deduplication, retry tests and live delivery check |
| P1 | User validation + deck copy | Us/product, team recruits participants | 5 observed task sessions first; then exploratory interviews; results and counterexamples recorded; slide claims match evidence and implementation |
| P2 | Better audience/mood ranking | Recommendation owner | Real independently labelled evaluation set; false exclusions checked; transient mood separated from long-term taste; measured improvement over simple baseline |

The current branch owns budget planning, its standalone interface and reviewed copy,
as requested by the user. Keep the existing ranking approach. Coordinate authenticated
MAX wiring with the backend owner; do not duplicate or replace their bot work.

## Remaining concrete risks found in source

- `parse_update` handles messages/callbacks but not `bot_started`; callback IDs are
  discarded and `/answers` is not called. Confirm platform behaviour with a token.
  Official reference: [callback answer](https://dev.max.ru/docs-api/methods/POST/answers).
- The webhook has no secret check and accepts arbitrary user IDs in supplied updates.
  Before public deployment, validate subscriptions' secret and handle duplicate delivery.
- Sending uses synchronous HTTP inside the async webhook; no delivery queue or retry
  policy. Polling can loop rapidly on failures. These matter once deployed.
- The catalogue parser takes only the first place, allows missing prices to become
  zero and accepts naive/offset datetimes without normalization. Validate real records
  and define one timezone contract before enabling a live feed. Plans skip unknown
  durations, but that does not fix all catalogue parsing problems.
- The children filter drops every <=6-rated theatre show, which can reject suitable
  shows. Legal minimum age is not target audience. Test independently labelled data.
- Mood is added to the persisted taste vector, so “tonight's mood” can accumulate.
  Treat it as a session overlay in a later ranking change.
- Standard interests/time questions have permissive fallback handling. Consider a
  shorter optional quiz and explicit invalid-input recovery in the next UX pass.
- Catalogue label generation at startup is rules-based, not a model call. Some docs
  describe richer LLM/embedding features that are not implemented.
- The planner sees only top-30 events and their supplied slots. It may miss feasible
  combinations involving other times/events. The UI must not call it an optimum.
- Prior SQLite report timestamps were rewritten on every message. Ask existing pilot
  users to confirm balances once; do not treat legacy timestamps as fresh evidence.

## Verification and how to reproduce

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python -m pytest backend/app/tests -q
docker compose up --build
```

Compose requires a version supporting optional `env_file` entries (2.24+). Without
tokens, this checks local startup and `/health`, not conversations inside MAX.
OpenAPI is served at `/openapi.json`. SQLite lives in the named `bot-state` volume;
`docker compose down` retains it. Don't add `-v` unless deliberately deleting it.

Before the UI contribution, the Python test run was **79 passed** (local and Docker).
The expanded suite now has **112 passed** locally (Python 3.13) and inside the product
image (Python 3.12); one dependency deprecation warning
from Starlette's HTTPX test adapter, no failed assertions. Tests cover shared/cinema
budgets, invalid/unknown input, restart, report-date stability, schedules, duplicate
productions, text size, variable prices and actual FastAPI startup against the fixture.
`docker compose config --quiet` passes without a local `.env`. The product image now
builds React in a Node stage and serves its static files from Python; the separate
browser-test image is not part of deployment. No token is needed for these checks.

Browser suite: **20 passed** in isolated Linux Chromium, across desktop and mobile
viewports. Covers preference-sheet apply/cancel, keyboard focus restoration, strict
budgets, loading, retries, empty/expired states, 320px dark layout and real Python API
requests (one per viewport). Native macOS browser launch was unavailable in the local
sandbox, so the reproducible fallback is `frontend/Dockerfile.test`. This is not a
Safari/MAX-device certification. The app was also visually inspected in the in-app
browser. Frontend production build and formatter check pass.

Image builds successfully. The uncached dependency-install layer took about 19 seconds
on this machine; this alone is not a portable full-build-time guarantee. No MAX token
or ProCulture key was used. Current data remains synthetic and ticket availability
is unverified. A complete live MVP still needs the P0 packages above.

## Message for the team

> Посмотрели актуальный код: бот, ранжирование и SQLite уже есть. В отдельной ветке
> добавили сборку планов из 2–3 событий, корректный учёт общего остатка и кино-лимита,
> обработку неизвестных сумм и проверки сценария. Исследование и продуктовые тексты
> доработали с разделением фактов, гипотез и ещё не реализованных возможностей.
> Уже сделали React-интерфейс этих планов и stateless API, без доступа к профилям
> бота. Формы и нижние окна — в привычной структуре мессенджера; тексты и состояния
> собраны отдельно. До живого демо приоритетны реальный каталог, HTTPS и проверка
> внутри MAX. Напоминания и синхронизация профиля пока остаются отдельными задачами.
