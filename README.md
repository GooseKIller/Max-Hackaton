# Max-Hackaton — Pushkin Card leisure assistant

A MAX bot that helps young people (14–22) spend their Pushkin Card on events they will
actually enjoy — before the money expires on 31 December.

**Status: research. The MVP scope is not fixed yet.**

## Decisions made so far

| Decision | Value |
|---|---|
| Track | Leisure and Entertainment |
| Audience | Pushkin Card holders, 14–22 |
| Pilot region | Kazan / Republic of Tatarstan |
| Backend | Python + FastAPI |
| Front end | React (MAX UI) |
| Scope (bot only vs bot + mini app) | **open** |

## Documentation

| Document | What's in it |
|---|---|
| [docs/requirements.md](docs/requirements.md) | What the hackathon requires: constraints, submission checklist, scoring weights |
| [docs/research/pushkin-card.md](docs/research/pushkin-card.md) | The program, the numbers, the pain, and what data we can actually get |
| [docs/research/hypothesis-boring-events.md](docs/research/hypothesis-boring-events.md) | Testing "the events are boring": what held up, what didn't, and the reframed product idea |
| [docs/design/ranking.md](docs/design/ranking.md) | How we rank events: why collaborative filtering won't work, and what to do instead |
| [docs/design/emotional-anchors.md](docs/design/emotional-anchors.md) | Why people actually go: narrative transportation, mood vs emotion, and the bridge mechanic |
| [docs/design/tone.md](docs/design/tone.md) | Why trying to sound young backfires, and the register rules that follow |
| [docs/research/max-platform.md](docs/research/max-platform.md) | MAX Bot API, mini apps, and which part of the flow goes where |
| [data/README.md](data/README.md) | The synthetic Kazan catalogue: why it exists, how it's shaped, what the funnel shows |
| [docs/outreach/api-key-request.md](docs/outreach/api-key-request.md) | Draft letter requesting the PRO.Культура.РФ API key, plus the fallback routes |
| [docs/brief/brief-ru.md](docs/brief/brief-ru.md) | The organizers' original brief (Russian, parsed from PDF) |

## Key facts to keep in mind

- We **cannot read a user's card balance** — no public API. The user tells us.
- We **cannot sell tickets** — we hand off to the official purchase link.
- The annual limit is policy that changed this year (5,000 → possibly 7,000 RUB).
  It must be configuration, never hardcoded.
- Cinema has its own separate sub-limit. Two budgets, not one. Cinema money gets spent
  easily (~40% of funds, hitting the cap); the other ~3,000 RUB is where money dies.
- **55% of cardholders are 15–18.** Design for a 16-year-old high schooler.
- Cool events outside the program **cannot** be paid with the card — the program is
  gated by an Expert Council. Our job is ranking what's already inside, not finding
  what's outside.

## Open action items

- [ ] Send the PRO.Культура.РФ key request (`partners@team.culture.ru`) — draft ready, needs team details
- [ ] Submit the opendata.mkrf.ru key form in parallel — lower bar, may arrive first
- [ ] Verify the current card limit and whether circuses are now included
- [x] Synthetic Kazan catalogue in the real API schema, so the build isn't blocked on a key
- [ ] Replace every synthetic number with real ones once a key arrives — and say so on the slides
- [ ] Survey 20–40 people aged 14–22 in Kazan — include the bare-vs-bridged A/B and the three-register cringe test
- [ ] Get 5 people aged 15–18 to read every user-facing string before submission
- [ ] Read the full MAX docs and confirm proactive messaging + mini app launch from a button
- [ ] Fix the MVP scope
