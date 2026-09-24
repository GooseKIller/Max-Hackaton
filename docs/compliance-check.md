# Compliance check against the brief

Re-read of the constraints, 24 September 2026, with our current plan checked against
each one. Source: [brief/brief-ru.md](brief/brief-ru.md), section ОГРАНИЧЕНИЯ, plus
ФОРМАТ СДАЧИ.

Legend: ✅ fine · ⚠️ needs action · ❓ open question

---

## The stack question

**❓ raised: "the brief says JS and React"**

It does not require them. Exact wording, [brief-ru.md:90](brief/brief-ru.md):

> «Для работы с мессенджером MAX **советуем** использовать JavaScript и React.
> **Допускается использование других языков программирования и API.**»

"Советуем" is a recommendation, and other languages are explicitly allowed. Python +
FastAPI on the backend is compliant.

The only place web technologies are effectively mandatory is the mini app itself:

> «Мини-приложения работают на базе стандартных веб-технологий: HTML, JavaScript и CSS.»

That is a statement of fact about how mini apps work — they are web apps — not a
restriction on the backend. Our plan already uses React + MAX UI there, which matches
the recommendation exactly.

**Verdict: ✅ no change needed.** And see "Own API" below — FastAPI turns out to
satisfy a submission requirement for free.

---

## Constraints, one by one

| # | Constraint | Status |
|---|---|---|
| 1 | Fits the leisure track, problem relevance argued | ✅ evidence collected |
| 2 | MAX is the environment; main scenario checkable in MAX | ✅ by design |
| 3 | **Works in both mobile and web MAX** | ⚠️ see below |
| 4 | JS/React recommended, others allowed | ✅ |
| 5 | Bot, or bot + attached mini app | ✅ scope still open |
| 6 | **Mini app attached to the bot, not an isolated service** | ⚠️ see below |
| 7 | Own API optional, no points by itself | ❓ see below |
| 8 | **No closed libraries, private APIs, unlicensed code** | ⚠️ see below |
| 9 | No secrets in the repo | ✅ `.gitignore` covers `.env`; `.env.example` still to write |
| 10 | Russian law, MAX rules, hackathon rules | ✅ |
| 11 | **Declare test/simulated data** | ⚠️ partially done |
| 12 | Bot username cannot be changed after creation | ⚠️ not yet decided |
| 13 | Source frozen after the deadline | ✅ |

---

## ⚠️ 1. Both mobile and web MAX

> «Функциональность проекта должна быть доступна пользователям в обеих версиях
> платформы.»

This is a hard requirement and it is easy to fail by accident — a mini app that works
in the mobile client and breaks in the web one costs us the "works end to end"
criterion, which is 30% of the technical score.

MAX Bridge reports the launch platform (iOS, Android, desktop, web), so adaptation is
supported. But it has to be tested on both, not assumed.

**Action:** test the full scenario in web MAX and mobile MAX before submission, and say
in the README that both were checked.

## ⚠️ 2. The mini app must hang off the bot

> «Мини-приложение в MAX подключается к чат-боту и не используется как изолированный
> от него сервис.»

Our design is fine here — onboarding and reminders live in the bot, the swipe feed and
planner in the mini app — but the *entry point* must be a button in the bot, and the
mini app must carry the bot's user context. A mini app reachable by URL alone, with its
own separate login, would violate this.

**Action:** confirm from the MAX docs how a button opens a mini app and what user
identity the mini app receives. Already an open item in
[research/max-platform.md](research/max-platform.md).

## ⚠️ 3. "No closed libraries, private APIs, unlicensed code"

Checked each dependency we have proposed:

| What | Status |
|---|---|
| `rubert-tiny2` | **MIT** ✅ |
| PRO.Культура.РФ API | ✅ official state platform, and the brief itself lists it as a recommended source |
| Our synthetic catalogue | ✅ ours |
| MAX Bot API / MAX UI / MAX Bridge | ✅ the platform we are told to build on |
| **A commercial LLM API** | ❓ **this is the real question** |

We proposed using an LLM for two things: labelling each event's emotional register, and
writing the bridge explanations. If the running solution calls a commercial LLM over the
network, that is arguably a private API, and it also adds an external dependency the
judges cannot reproduce inside Docker.

**The fix resolves three problems at once.** Move all model work **offline**:

- run affect labelling and embedding once, as a build-time/authoring step,
- ship the resulting labels and vectors as data files,
- the container serves precomputed artifacts and calls no model at runtime.

This means:
- ✅ no private API dependency in the delivered solution,
- ✅ Docker build stays well under the **5-minute limit** — no model download, no
  weights in the image,
- ✅ reproducible for a judge with no API key of ours.

If we still want live LLM-written explanations, make it an optional enhancement that
degrades to templated text when no key is configured, and document it as an external
service per the brief's instruction about services that cannot run inside Docker.

**Action:** treat "no ML at runtime" as an architectural rule, not a preference.

## ⚠️ 4. Declaring synthetic data

Done in [../data/README.md](../data/README.md). Not yet done in the two places that are
actually graded:

- **the submitted root README** — required content list includes "описание работы с
  данными" and "порядок работы с тестовыми данными",
- **the presentation slides** — "ограничения, риски и ключевые допущения".

**Action:** carry the disclaimer into both when they are written.

## ⚠️ 5. The bot username

One-shot, irreversible decision. Worth ten minutes of thought and a team vote rather
than whatever gets typed at 3am on deadline night.

## ❓ 6. Do we count as "a solution with its own API"?

This matters because it drags in real extra work. If we do, we additionally owe:

1. a checkable HTTPS address,
2. `openapi.yaml` or `openapi.json` (OpenAPI 3.0/3.1),
3. test accounts per role,
4. test data,
5. `DATA-API.yaml` listing the mandatory checks — config version, team id, base URL,
   endpoints with method and path, request parameters, required role, expected status
   codes, expected response shape.

A mini app needs a backend, so we will have HTTP endpoints. The safe reading is that
this counts, and we should produce these artifacts rather than argue about it.

**The good news, and it is a point in favour of the stack that prompted this review:**
FastAPI generates OpenAPI 3.1 automatically at `/openapi.json`. Requirement 2 is free.
Only `DATA-API.yaml` is hand-written, and it is a short file.

Note also: having an API earns **no points by itself**. So expose exactly what the mini
app needs and nothing more — every extra endpoint is another thing that must work
correctly under the "integration and data exchange" criterion (20%).

---

## Submission artifacts not yet started

From ФОРМАТ СДАЧИ. None of these are blocked; they just need writing.

- [ ] Root `README.md` with all 15 required sections
- [ ] `Dockerfile` for each locally-run component
- [ ] `compose.yaml` — everything up with **one command**
- [ ] `.dockerignore`
- [ ] `.env.example` with no real values
- [ ] `requirements.txt` / `package-lock.json` with pinned versions
- [ ] `openapi.json` (free from FastAPI) and `DATA-API.yaml` (manual)
- [ ] Presentation PDF, with the technical slide 1
- [ ] Measure the Docker build and confirm it is under 5 minutes

## Summary

The stack was never the problem. The three things actually worth acting on are:

1. **No ML at runtime** — move labelling and embedding offline. Fixes the private-API
   question, the 5-minute build limit and reproducibility together.
2. **Test in both mobile and web MAX** — a silent way to lose 30% of the technical score.
3. **Carry the synthetic-data disclaimer** into the submitted README and the slides,
   not just into `data/README.md`.
