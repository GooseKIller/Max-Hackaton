# Budget planner UI

React + TypeScript, served by the existing Python application at `/app/`. Compact
messenger-style controls, not a marketing landing page: system font, inset settings
rows, bottom sheets for preferences and details. Blue action colour plus violet/pale
pink cultural accents is our interpretation of the MAX / Pushkin Card combination,
not an official co-brand palette or copied brand assets. Light/dark
system preference, keyboard focus and reduced motion are supported. No copied logos,
external fonts, stock images, tracking pixels or frontend secrets.

## Run

From the repository root, the complete build needs only Docker:

```bash
docker compose up --build
```

Open `http://localhost:8000/app/`. The catalogue is synthetic; the demo explicitly
disables seller links. Never present it as real ticket availability.

For frontend work, use Node 22.12+ and pnpm 11.19.0:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

In another terminal, from the repository root:

```bash
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open `http://localhost:5173/app/`; Vite proxies `/api` to port 8000. `pnpm build`
type-checks and creates `frontend/dist`, ignored by Git. When using the built files,
build **before** starting Python, then reload the page after subsequent builds.

## Contract and privacy

- `GET /api/planner/meta`: supported city, synthetic status, categories, limits and sources.
- `POST /api/planner/plans`: strict explicit age, total balance, optional cinema
  remainder, category list and availability. OpenAPI: `/openapi.json`.
- No user ID, auth token, database profile access or writes. Requests use POST; money
  is not placed in URLs. Responses use `Cache-Control: no-store`. Form state stays
  in React memory and is cleared when the page is closed/reloaded; no localStorage.
- `categories: []` means all formats subject to the other filters. `prochie` includes
  catalogue categories without a dedicated chip. Unknown cinema excludes cinema.
- Editing any input removes the old result. Loading disables duplicate submission.
  Errors preserve the inputs. Empty plans can still offer individually affordable
  events; their combined price has **not** been approved as a plan.
- Preferences are edited in a bottom sheet. “Готово” applies the draft; close/Escape
  discards it and restores focus to the opening control.
- No hidden fixed demo date. The server uses Kazan local time and the configured
  planning horizon; once the catalogue ages, show an empty/expired state.

Example request:

```json
{"age":18,"balance":3000,"cinema_balance":null,"categories":[],"availability":"both"}
```

`plans[].events` contains title, venue/address, start/end, price/minimum flag, age and
a nullable safe HTTPS seller URL. The response includes aggregate cost, cinema cost,
remainder and calculation time. All plans are alternatives, not a shared basket.

## MAX boundary

The official [MAX Bridge](https://dev.max.ru/docs/webapps/bridge) script is loaded
asynchronously; the ordinary browser UI remains functional if it is unavailable.
In a MAX context, seller clicks use `WebApp.openLink`; an open details sheet hooks
the native BackButton. No unsupported `ready()` call or Telegram API is assumed.

This is a **standalone, stateless web interface**, ready for integration work, not a
verified signed-in MAX mini-app. Backend now supports an opt-in open_app button via
MINI_APP_BOT; leave it empty until registration. The team must register its HTTPS URL in the bot
settings and test iOS/Android/web MAX. See [official setup](https://dev.max.ru/docs/webapps/introduction).
Before syncing saved bot profiles, validate MAX `initData` server-side and derive
identity there. Never trust `initDataUnsafe.user.id` or a query-string ID. MAX UI
components are not a dependency in this contribution; styling uses standard HTML/CSS.

Before public deployment: configure a reverse-proxy request-size limit and rate
limits; avoid logging request bodies; review legal/privacy text; verify the real
catalogue city and seller links. The bot webhook now requires a secret, validates
input, acknowledges callbacks and persists retry receipts. See ../docs/deployment.md
for remaining deployment checks. No deployment is implied by a local UI demo.

## Tests

Build and run Python first as above. Then, from `frontend/`:

```bash
pnpm exec playwright install chromium
pnpm test
pnpm run format:check
```

`PLAYWRIGHT_CHANNEL=chrome pnpm test` can use an installed Chrome. Browser tests
cover desktop and mobile-sized Chromium, including dark 320px layout, loading,
validation, errors/retry, modal focus and empty results. Most state tests use fixed
HTTP responses; one test per viewport calls the real Python API. This is **not**
evidence of native MAX compatibility or Safari testing.

Isolated Linux alternative (run from repository root):

```bash
docker build -f frontend/Dockerfile.test -t max-hackaton-planner-tests .
docker run --rm --shm-size=1g \
  -e PLANNER_BASE_URL=http://host.docker.internal:8000 \
  -v "$PWD/frontend/test-results:/tests/test-results" \
  max-hackaton-planner-tests
```

On Linux Docker, add `--add-host=host.docker.internal:host-gateway` and make the test
server reachable on that host interface. Keep it local, without production credentials.
The browser test image is separate from the product image and is not deployed.
