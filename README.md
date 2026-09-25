# Max-Hackaton — Pushkin Card leisure assistant

A MAX bot that helps young people (14–22) spend their Pushkin Card on events they will
actually enjoy — before the money expires on 31 December.

**Status: first working bot. The MVP scope is not fixed yet.**

The contribution in this branch adds budget-aware 2–3-event plans to the existing
bot. It uses **synthetic events with no working ticket purchases**. MAX mobile/web
integration and real catalogue access still require testing with the team's keys.
See the [current audit and work packages](docs/development-audit.md) and
[research review](docs/research/validation.md).

```bash
python3 backend/console.py
```
Runs the whole conversation in a terminal — no MAX token needed.
See [backend/README.md](backend/README.md).

## Decisions made so far

| Decision | Value |
|---|---|
| Track | Leisure and Entertainment |
| Audience | Pushkin Card holders, 14–22 |
| Pilot region | Kazan / Republic of Tatarstan |
| Backend | Python + FastAPI (allowed — JS/React is a recommendation, not a requirement) |
| Front end | React (MAX UI) |
| Scope (bot only vs bot + mini app) | **open** |

## Documentation

| Document | What's in it |
|---|---|
| [docs/design/takes.md](docs/design/takes.md) | Reviewed product positioning and Russian copy, with implementation status |
| [docs/research/validation.md](docs/research/validation.md) | Evidence register, corrected inferences and interview/experiment protocol |
| [docs/development-audit.md](docs/development-audit.md) | What exists, what is missing, priorities and contribution boundaries |
| [docs/design/budget-plans.md](docs/design/budget-plans.md) | Planner contract, constraints and reproducible demo |
| [docs/compliance-check.md](docs/compliance-check.md) | Our plan checked against every constraint, with what still needs doing |
| [docs/requirements.md](docs/requirements.md) | What the hackathon requires: constraints, submission checklist, scoring weights |
| [docs/research/pushkin-card.md](docs/research/pushkin-card.md) | The program, the numbers, the pain, and what data we can actually get |
| [docs/research/hypothesis-boring-events.md](docs/research/hypothesis-boring-events.md) | Testing "the events are boring": what held up, what didn't, and the reframed product idea |
| [docs/design/database.md](docs/design/database.md) | The schema, and why the taste vector already *is* a user embedding |
| [docs/design/ranking.md](docs/design/ranking.md) | How we rank events: why collaborative filtering won't work, and what to do instead |
| [docs/design/emotional-anchors.md](docs/design/emotional-anchors.md) | Why people actually go: narrative transportation, mood vs emotion, and the bridge mechanic |
| [docs/design/tone.md](docs/design/tone.md) | Why trying to sound young backfires, and the register rules that follow |
| [docs/research/max-platform.md](docs/research/max-platform.md) | MAX Bot API, mini apps, and which part of the flow goes where |
| [docs/testing-in-max.md](docs/testing-in-max.md) | How to get a token and actually run the bot inside MAX |
| [backend/README.md](backend/README.md) | How to run the bot, how the modules fit together, known limitations |
| [data/README.md](data/README.md) | The synthetic Kazan catalogue: why it exists, how it's shaped, what the funnel shows |
| [docs/outreach/api-key-request.md](docs/outreach/api-key-request.md) | Draft letter requesting the PRO.Культура.РФ API key, plus the fallback routes |
| [docs/brief/brief-ru.md](docs/brief/brief-ru.md) | The organizers' original brief (Russian, parsed from PDF) |

## Key facts to keep in mind

- We **cannot read a user's card balance** — no public API. The user tells us.
- We **cannot sell tickets** — we hand off to the official purchase link.
- The official programme page lists **5,000 RUB for 2026**, including up to **2,000
  RUB on cinema**. Rules live in configuration with a source and review date.
- There is one total balance and a remaining cinema sub-limit inside it. We ask for
  both; unknown cinema means recommendations without cinema, unknown total means
  browsing without funded plans. No statistical claim about typical leftover money.
- A 15–18-year-old in Kazan is a **proposed pilot segment**, to validate in interviews.
  Regional age statistics are not a nationwide distribution.
- Cool events outside the program **cannot** be paid with the card — the program is
  gated by an Expert Council. Our job is ranking what's already inside, not finding
  what's outside.

## Open action items

- [ ] Send the PRO.Культура.РФ key request (`partners@team.culture.ru`) — draft ready, needs team details
- [ ] Submit the opendata.mkrf.ru key form in parallel — lower bar, may arrive first
- [ ] Verify the current card limit and whether circuses are now included
- [x] Review the official 2026 limit: 5,000 RUB, including up to 2,000 on cinema
- [x] Synthetic Kazan catalogue in the real API schema, so the build isn't blocked on a key
- [ ] Replace every synthetic number with real ones once a key arrives — and say so on the slides
- [ ] Survey 20–40 people aged 14–22 in Kazan — include the bare-vs-bridged A/B and the three-register cringe test
- [ ] Get 5 people aged 15–18 to read every user-facing string before submission
- [ ] Read the full MAX docs and confirm proactive messaging + mini app launch from a button
- [ ] Fix the MVP scope
- [x] Step 1 of the build plan: hard filters, dialog, MAX client, Docker
- [x] Steps 2-3: affect labelling, taste vectors, ranking with diversity, onboarding quiz
- [x] SQLite store: profiles, taste vectors, interaction log, session state, catalogue cache
- [x] Plans in the bot: 2–3 events, aggregate budgets, schedule checks, estimated prices
- [x] Unknown balances preserved; user-report date does not advance on every interaction
- [ ] Measure the Docker build against the 5-minute cap (Docker wasn't running here)
- [ ] **Ask the organizers when the bot token is handed over** — everything MAX-side depends on this
- [ ] Backup: if anyone on the team is self-employed, start a bot through business.max.ru (48h moderation)
- [ ] Verify the MAX keyboard payload shape against a live token
- [ ] Architectural rule: no ML at runtime — label and embed offline, ship artifacts
- [ ] Test the full scenario in **both** mobile and web MAX
- [ ] Pick the bot username (irreversible)
