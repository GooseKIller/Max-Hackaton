# Research: the Pushkin Card and where it hurts

Status: research notes, September 2026. Written before we fixed the MVP scope.

**Review, 25 September:** use [validation.md](validation.md) for the reviewed evidence
register. Scale, regional adoption and app-rating figures below remain source leads
unless explicitly checked there. They must not become presentation facts by repetition.

This file separates three things on purpose, because the track brief demands it:

- **Fact** — taken from an official source or a source we could check.
- **Signal** — reported by media or user reviews; directionally useful, not proof.
- **Assumption** — our own guess. Must be validated before we build on it.

---

## 1. How the program works

**Fact.** The Pushkin Card is a state program. Russian citizens aged 14 to 22 get a
card with money on it that can only be spent on cultural events — theatres, museums,
concerts, exhibitions, cinema.

**Fact.** In 2026 the card holds **5,000 RUB per year**, of which **2,000 RUB may go to
cinema**. Source: the official culture.ru program page.

**Unverified policy lead, not a current rule.** Media reported a draft that raises
the limit to **7,000 RUB from 1 September 2026**, adds **state circuses** as an allowed
category with a cap of 2,000 RUB, and keeps the 2,000 RUB cinema cap. At the time we
checked, the draft was in public discussion and the official culture.ru page still
showed 5,000 RUB.
→ **Action item: verify the current limit before the submission.** Our product must not
hardcode it — see "What this means for the product" below.

**Fact.** Unused money **expires on 31 December** and does not roll over. The card is
topped up again in January.

**Fact.** To get the card a user registers on Gosuslugi, confirms the account, installs
the "Gosuslugi Kultura" app, and receives a virtual or physical Mir card. Tickets are
bought in that app, on partner websites, or at venue box offices.

**Fact.** There is **no public API to read a user's card balance**. Balance is visible
only inside Gosuslugi Kultura, the Gosuslugi portal, or VTB's own banking apps.
This is the single most important technical constraint we found.

---

## 2. How big it is

| Metric | Value | Period | Source type |
|---|---|---|---|
| Program participants | 13.02 million | end of 2025 | Accounts Chamber materials |
| Participants a year earlier | 11.32 million | end of 2024 | same |
| Participating institutions | 12,550 (up from 12,128) | 2025 | same |
| State subsidy | 10.59 bn RUB | 2025 | same |
| Tickets sold | ~102 million (+30% YoY) | 2025 | industry reporting |
| Cards/tickets in an earlier draft | withheld | mismatched source/period | original reporting required; do not derive purchases per user |

**Signal.** Roughly 5,000 RUB × 13 million people is a ~65 bn RUB annual pool of
"must be spent on culture, or it disappears" money. The 10.59 bn RUB subsidy figure
suggests actual drawdown is far below the theoretical maximum — but we could **not**
find an official statistic for the share of balances left unspent.
→ **Action item: this gap is our core problem claim. Look for a Ministry of Culture or
Accounts Chamber breakdown, or collect our own evidence via a survey of 14–22 year olds.**

---

## 3. Tatarstan and Kazan — our pilot region

**Fact/Signal** (regional media citing the Ministry of Culture of Tatarstan):

- About **403,000 active cardholders** — 4th place in Russia.
- **69% of all 14–22 year olds** in the republic have the card.
- **Renewal rate 70%**, against a national average of 51%.
- About **116,700 registered participants under 18** (Ministry of Education of Tatarstan).
- Reported 100% coverage of school students.

**Why this matters.** Tatarstan is not a region with a card adoption problem. Almost
everyone who can have the card already has one, and they keep renewing it. So the
remaining problem is **not "get a card"** — it is **"use it well."** That is a much
better problem for us: the audience already exists and is already activated.

Kazan is also where the final is held on 29 October, so the jury knows the local venues.

---

## 4. The actual pain

What we can support today:

**Signal — the year-end rush is real.** Media reported that youth spending on the card
**doubled over the New Year holidays**. Regional authorities publicly campaign every
December asking young people to "zero out" their cards before 31 December. People are
not pacing their spending across the year; they panic in December and buy whatever is
left, which is usually whatever is least interesting.

**Signal — the existing tools are weak.** The official Gosuslugi Kultura app sits at
4.5★ on RuStore with ~1,280 reviews, but Google Play reviews are much harsher. The
recurring complaints are: the event listing feels limited or stale, and in some flows
users cannot actually pay with the card from inside the app.

**Signal — discovery is the bottleneck, not supply.** With 12,550 participating
institutions, the problem is not that there is nothing to attend. The problem is that
a 17-year-old in Kazan opens an app, sees a flat chronological list of everything, and
has no way to answer "which of these would *I* actually enjoy, this Saturday, within my
remaining balance, near where I live?"

**Assumption (needs validation).** The user's real decision has at least five variables
at once — interest, remaining balance, cinema sub-limit, date/time, and travel distance
— and no existing tool helps hold all five at once. The brief itself names exactly this
pattern as a good problem to attack.

**Assumption (needs validation).** A meaningful share of users never spend the cinema
portion or never spend the non-cinema portion, because the two sub-limits are invisible
until checkout.

→ **Action item: run a short survey with 20–40 people aged 14–22 in Kazan.** Five
questions is enough: do you have the card, what is on it right now, when did you last
use it, what did you spend the leftover on last December, what stops you from using it
more. This converts our assumptions into evidence, which is a scored criterion.

---

## 5. Data we can actually get

This is the good news. There is a real, official, machine-readable source.

### PRO.Культура.РФ export API (version 2.5)

**Fact.** There is a dedicated endpoint for exactly our events:

```
GET https://pro.culture.ru/api/2.5/pushkinsCardEvents?apiKey=<KEY>&<params>
```

The collection contains **only events approved for the Pushkin Card program**. JSON
response. We verified by request that it returns `403 Access denied` without a key.

Useful filters:

| Parameter | What it does |
|---|---|
| `subordinations` | region, recursive — one id gives a region and all its cities |
| `locales` | exact locale (city) ids |
| `categories` | `vystavki`, `koncerty`, `spektakli`, `ekskursii`, `kino`, `obuchenie`, `vstrechi`, `prazdniki`, `prochie` |
| `organizationCategory` / `placeCategory` | `teatry`, `muzei-i-galerei`, `kinoteatry`, `cirki`, `parki`, … |
| `start` / `end` | date range, unix timestamps in ms |
| `free` | free vs paid only |
| `tags` | genre-style tags with ids |
| `nameQuery` | text search by title |
| `status=accepted` | confirmed events only |
| `limit` / `offset` | max 100 per page |

Fields we get per event — this is enough to build a real recommender:

- `name`, `shortDescription`, `description`, `ageRestriction`
- `category` and `tags` (genre-like, with ids and names)
- `isFree`, `price`, `maxPrice`
- `saleLink` — **a direct link to buy the ticket**
- `image`, `gallery`
- `places[]` with `seances[]` (every showtime, start and end, local and UTC),
  full FIAS address (region / city / street / house), `coordinates`, and `locale`
- `accessible[]` — accessibility codes, including `e1`: a combined ticket for a
  disabled visitor and their companion when paying with the Pushkin Card

There are companion endpoints: `/organizations`, `/categories`, `/locales`.

**How to get a key.** Email `partners@team.culture.ru` and request an integration key.
→ **Action item: send this request today. It is the longest-lead item we have.**

### Ministry of Culture open data portal

**Fact.** `opendata.mkrf.ru` publishes the same PRO.Культура.РФ events as an open
dataset (`7705851331-events`), JSON and XML, updated weekly. Its `v2` API returned
`401` without a key; a key is requested through a form on the site and is emailed back,
apparently quickly.

### Our fallback if no key arrives in time

Prepare a **frozen snapshot of real Kazan events** as a seed dataset, and make the data
layer swappable behind one interface. The brief is explicit about this: if we use
prepared or synthetic data instead of a live integration, we must **say so clearly** in
the README and the presentation, and describe what is needed to make it real. Faking an
integration is called out as a mistake.

---

## 6. What this means for the product

Constraints we now know are hard:

1. **We cannot read the card balance.** The user must tell us what is on their card.
   Design around it: ask once, remember it, let them correct it, and treat it as
   "user-reported, not verified." Do not pretend it is live data.

2. **We cannot sell tickets.** We can only send the user to the official `saleLink` or
   to Gosuslugi Kultura. Our value ends at "here is the right event, here is the button
   to buy it" — and that is fine, that is the honest scope of a discovery product.

3. **The limits change.** 5,000 vs 7,000 RUB, the cinema cap, the new circus cap — all
   of these are policy that moved this year. Limits must be **configuration, not code**,
   with a visible "rules as of <date>, source: <link>" line in the UI. The brief scores
   us on showing data provenance and freshness.

4. **One total balance and a cinema sub-limit inside it.** All ticket costs count
   toward the total; cinema costs also count toward its remaining allowance. The
   planner must check both, including previous cinema spending reported by the user.

Where the opportunity is:

The card is not a discovery problem *in general* — it is a **budget-aware, taste-aware
planning problem with an expiry date**. Nobody is solving the "you have 3,200 RUB left,
it disappears in 68 days, here is a plan that spends it on things you'll actually like"
job. That framing is narrower than "find events", which is what the brief asks for, and
it is the one thing the official app does not do.

---

## 7. Open questions before we lock the scope

1. Is the limit 5,000 or 7,000 RUB right now, and are circuses in?
2. Can we get the PRO.Культура.РФ key in time? (Ask now.)
3. How many Pushkin Card events does Kazan actually have in a given week? This decides
   whether the problem is "too much choice" or "too little" — and the product changes
   completely depending on the answer.
4. Do we have any way to reach 14–22 year olds in Kazan for a quick survey?
5. Which part of the flow belongs in chat and which needs a mini app? (See
   [max-platform.md](max-platform.md).)

---

## Sources

- [Pushkin Card — official program page, Культура.РФ](https://www.culture.ru/pushkinskaya-karta)
- [Ministry of Culture draft: limit raised to 7,000 RUB from 1 Sept 2026, circuses added (July 2026)](https://116.ru/text/culture/2026/07/07/76521674/)
- [Program scale figures, Accounts Chamber / industry reporting](https://www.tadviser.ru/index.php/Статья:Пушкинская_карта)
- [Youth spending doubled over the New Year holidays, Izvestia, Jan 2026](https://iz.ru/2023868/2026-01-13/v-novogodnie-prazdniki-molodezh-udvoila-traty-po-pushkinskoi-karte)
- [Tatarstan among the top regions by cardholders, Tatar-inform](https://www.tatar-inform.ru/news/tatarstan-vosel-v-top-5-regionov-rf-po-cislu-aktivnyx-polzovatelei-puskinskoi-karty)
- [Over 70% of Tatarstan youth renewed the card](https://yutazy.ru/news/obschestvo/bolee-70-molodezi-tatarstana-prodlili-puskinskuiu-kartu-respublika-v-top-2-rossii)
- [PRO.Культура.РФ export API documentation (PDF)](https://pro.culture.ru/documentation/export_API_PRO.pdf)
- [PRO.Культура.РФ export API page](https://pro.culture.ru/new/api/documentation/export)
- [Ministry of Culture open data: cultural events dataset](https://opendata.mkrf.ru/opendata/7705851331-events)
- [Gosuslugi Kultura app on RuStore (ratings and reviews)](https://www.rustore.ru/catalog/app/ru.gosuslugi.culture)
- [Gosuslugi FAQ on the Pushkin Card](https://www.gosuslugi.ru/help/faq/pushkin_card/1000751)
