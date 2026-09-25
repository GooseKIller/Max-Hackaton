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

## Best next work packages

Suggested ownership, to coordinate with the team before parallel edits:

| Priority | Package | Suggested owner | Done when |
|---|---|---|---|
| P0 | MAX integration hardening | Backend owner | Bot-start update handled; callbacks acknowledged; webhook secret validated; duplicate updates do not repeat actions; malformed updates cannot crash polling; verified in MAX mobile and web |
| P0 | Real pilot catalogue | Research/data owner | Checked source snapshot or working API key; Kazan filter confirmed; live prices, availability links and durations reviewed; source/retrieval time retained |
| P1 | Mini app for cards/plans | Frontend owner, with us on contract/tests | Bot opens app; server validates MAX initData; profile and plans load; loading/error/empty states work; explicit plan selection and seller click instrumentation |
| P1 | Reminder delivery | Us/backend after contract agreement | Explicit opt-in and opt-out, Moscow-time schedule, dated reported balance, per-user/year/rule deduplication, retry tests and live delivery check |
| P1 | User validation + deck copy | Us/product, team recruits participants | 5 observed task sessions first; then exploratory interviews; results and counterexamples recorded; slide claims match evidence and implementation |
| P2 | Better audience/mood ranking | Recommendation owner | Real independently labelled evaluation set; false exclusions checked; transient mood separated from long-term taste; measured improvement over simple baseline |

The current branch is the budget-planning and reviewed-copy contribution. Keep the
existing ranking approach; a frontend rewrite or a new recommendation architecture
would overlap other team work without first improving the core demo.

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

Local Python test run: **79 passed** (Python 3.13); one dependency deprecation warning
from Starlette's HTTPX test adapter, no failed assertions. Tests cover shared/cinema
budgets, invalid/unknown input, restart, report-date stability, schedules, duplicate
productions, text size, variable prices and actual FastAPI startup against the fixture.
Docker Python 3.12: **79 passed**, the same dependency warning. `docker compose
config --quiet` passes without a local `.env`. No token was needed for these checks.

Image builds successfully. The uncached dependency-install layer took about 19 seconds
on this machine; this alone is not a portable full-build-time guarantee. No MAX token
or ProCulture key was used. Current data remains synthetic and ticket availability
is unverified. A complete live MVP still needs the P0 packages above.

## Message for the team

> Посмотрели актуальный код: бот, ранжирование и SQLite уже есть. В отдельной ветке
> добавили сборку планов из 2–3 событий, корректный учёт общего остатка и кино-лимита,
> обработку неизвестных сумм и проверки сценария. Исследование и продуктовые тексты
> доработали с разделением фактов, гипотез и ещё не реализованных возможностей.
> Предлагаем взять на себя этот модуль, тексты/пользовательскую проверку и затем
> напоминания. По мини-приложению можем помочь с контрактом, состояниями и тестами;
> сначала согласуем границы с тем, кто делает интерфейс. До демо приоритетны реальный
> каталог и проверка бота в обеих версиях MAX.
