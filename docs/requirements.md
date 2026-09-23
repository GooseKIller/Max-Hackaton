# What the hackathon actually requires

An English summary of the "Leisure and Entertainment" track brief. The original is
[docs/brief/brief-ru.md](brief/brief-ru.md) (parsed from the organizers' PDF).
Where the two disagree, the original wins.

---

## The task

Build a **chat bot or a mini app on the MAX Business Platform** that solves a real
problem in leisure and entertainment. We choose the user and the problem ourselves —
there is no predefined list of products.

Two stages:

**Online stage — build the MVP**
1. Define the target audience and the priority user segment, and justify the choice.
2. Define a specific user problem and confirm it is real.
3. Design the UX and the main scenario: how the user starts, what they do, what they get.
4. Define the expected effect — which part of the current process improves, and by what
   measurable indicator.
5. Define the scaling potential and what is needed to roll it out further.
6. Build the MVP in MAX using the token the organizers give us.
7. Prepare the presentation and pass selection into the final.

**Offline stage — defend in front of the jury**
1. Work out a pilot launch and rollout scenario.
2. Refine the solution and prepare the demo and the pitch.
3. Defend in person on **29 October in Kazan**. Three prize-winning teams per track.

---

## Hard constraints

- The solution must fit the leisure/entertainment track, and the problem's importance
  must be argued, not asserted.
- **MAX must be the environment** for the product. The main scenario must be checkable
  inside MAX.
- It must work in **both the mobile and the web** versions of MAX.
- JavaScript and React are recommended; other languages and APIs are allowed.
- Allowed shapes: a chat bot, or a chat bot with a mini app attached. A mini app must be
  connected to the bot, not an isolated service.
- Having our own API is optional and **earns no points by itself**.
- No closed libraries, private APIs, or third-party code without a free-use licence.
- **No working tokens, passwords, API keys or other secrets in the repository.**
- Must comply with Russian law, MAX platform rules, and the hackathon rules.
- If the MVP uses test, prepared or simulated data instead of a real integration,
  **this must be stated explicitly** in the materials.
- A bot's username cannot be changed after creation.
- After the deadline the submitted source version is frozen.

---

## Submission checklist

**1. A working solution in MAX** — a link or other access method so a judge can run the
main scenario.

**2. A frozen source version** — a Git repository with a commit hash, or an archive with
a checksum.

**3. `README.md`**, containing all of:
- what the solution is for
- the main user scenario
- the components and architecture
- **one command** that starts every local component via Docker
- required environment parameters
- environment variables
- ports used
- dependencies
- external services and integrations
- how data is handled
- how to work with test data
- a step-by-step verification scenario
- examples of expected system behaviour
- known limitations
- how to stop and restart the solution

If the MVP needs an external service that cannot be reproduced inside Docker, describe
its purpose and what is needed to check the solution.

Containerisation does **not** replace the live product in MAX — the bot/mini app must
stay reachable.

**4. A dependency lock file** — e.g. `requirements.txt`, `package-lock.json`.

**5. Docker configuration** — in the repo:
- `Dockerfile` for every locally-run component
- `compose.yaml` / `docker-compose.yml` starting everything with one command
- `.dockerignore`
- `.env.example` with no real secrets

The Docker build must take **no more than 5 minutes** (excluding base image pulls) and
must not include unnecessary components or steps.

**6. A PDF presentation.**
- **Slide 1 is technical and is not graded**: link to the working bot/mini app, Git
  repo link and commit hash, own API address if any, test logins and passwords, working
  tokens and env values needed to run and check the solution, and a short walkthrough of
  the main scenario.
- From slide 2: solution name and team, executive summary, target audience, problem and
  its relevance, the solution and the main scenario, expected effect, architecture, data
  and integrations, scaling potential and adaptation conditions, limitations/risks/key
  assumptions, sources used.

**Only if we build our own API**, we additionally owe: the checkable HTTPS address, an
`openapi.yaml`/`openapi.json` (OpenAPI 3.0 or 3.1), test accounts per role, test data,
and a `DATA-API.yaml` listing the mandatory checks (config version, solution/team id,
API base URL, the list of endpoints with method and path, request parameters, required
role, expected status codes, expected response format).

---

## How we are scored

Every criterion is scored 0–3: not done / weak / partial / good.

### Disqualifying (score 0, not evaluated further)

- Off-topic, solves a different problem, or does not use MAX as the environment.
- The bot or mini app does not start, does not respond, or the main scenario cannot be
  checked.
- No presentation.

### Online stage

**Product score — 40% of the online stage total**

| Weight | Criterion |
|---|---|
| 35% | **Scaling potential** — concrete contexts/regions/organisations beyond the first case; directions that fit the product's logic; adaptation conditions (data, integrations, resources, product changes); key limits and risks; a realistic rollout order |
| 25% | **User value** — clear audience and priority segment; a specific, current need; a useful outcome for the user; an advantage over how they solve it today; demand backed by data, observation or argued assumptions |
| 20% | **UX/UI** — the main path matches the priority scenario; the sequence is understandable without explanation; key actions and navigation are easy to find; the interface reports loading, results and errors; no dead ends or redundant steps |
| 15% | **Coherence** — the solution fits the stated problem; problem → mechanics → outcome are logically linked; key decisions and assumptions are argued; features form one product; it is realistic under the given constraints |
| 5% | **Presentation quality** — structure, clarity, sufficiency, readable visuals, no padding |

Note the weighting: **scaling is the single heaviest product criterion at 35%.** It is
not a closing slide, it is the main event.

**Technical score — 60% of the online stage total**

| Weight | Criterion |
|---|---|
| 30% | **Works end to end** — the main scenario can be completed to the stated result; key functions work; API checks pass if we have an API |
| 20% | **Integration and data exchange** — components interact correctly and consistently; data and state are handled predictably; external integrations behave as described; API contract is honoured |
| 20% | **Technical implementation and architecture** — structure fits an MVP; components, roles and links are clear; key logic is separated so it can be maintained and extended |
| 10% | **Stability and error handling** — works on repeat runs; bad input is handled; the user can continue after an error without a full restart; no systematic failures or timeouts |
| 10% | **Security, dependencies and data** — no secrets in source; dependency versions pinned; data access matches the product's logic; data and external services documented; no obvious critical risks |
| 10% | **Technical documentation** — materials match the frozen version; the solution can be reproduced from the instructions; startup, architecture, dependencies, environment and integrations described; verification steps and expected results given; known limitations recorded |

**Platform bonus: +0.15**, all-or-nothing. Requires that the main scenario fully works
and is checkable, that we use a MAX capability beyond the minimum, and that this
capability creates user value, fits the product naturally, works end to end, and is
described in the materials. Having an API, more features, or the basic required
capabilities does **not** qualify.

### Final

40% technical score of the product + 60% the defence itself. The platform bonus does
**not** carry over.

Defence criteria: user value and fit (25%), scaling and replication potential (25%),
MVP and UX quality (20%), launch and rollout scenario (15%), quality of the defence and
answers (10%), team ownership of the solution (5%).

That last one matters: **every team member must own their area** and the answers must
not contradict each other.

---

## The brief's own advice

- **Name a concrete user and context.** "Leisure users" or "tourists" is not enough.
- **Prove the problem exists.** Use open data, official sources, research, interviews or
  argued assumptions — and separate confirmed facts from your own hypotheses.
- **Focus on one priority scenario** and implement it end to end. Do not try to cover
  the whole leisure domain.
- **Problem first, technology second.** A bot, a mini app or an LLM must serve the
  problem, not be the point.
- **Mind where data comes from and how fresh it is.** Prefer primary sources; check what
  territory and period the data covers; show the user the source and the as-of date.
- **Do not fake integrations.** If there is no real access, use prepared or synthetic
  data and say so, and describe what is needed to make it real after the MVP.
- **If using an LLM for rules or official information:** tie answers to sources, show
  the basis, handle the case where there is no reliable answer, and never present a
  model's guess as an official fact.
- **Treat scaling as moving to a new context.** Separate the product core (problem,
  scenario logic, architecture, base data model, interaction mechanics, key UI) from the
  variable part (event data, regional specifics, reference books, external systems,
  integrations, participant roles, participation rules).
- **A pilot is a first limited launch:** for whom and where, how it fits existing
  processes, what data/integrations/people are needed, how users get access, what
  metrics judge it, and what happens next.

## Official data sources the brief suggests

Культура.РФ (event listings), PRO.Культура.РФ (organiser side and data publishing),
AIS "Statistics" of the Ministry of Culture, the Unified Calendar Plan and the All-Russian
Register of Sports Facilities (Ministry of Sport), the national tourism portal
Путешествуем.рф, Добро.рф (volunteering), the Pushkin Card pages on Культура.РФ, and the
State Address Register / FIAS.
