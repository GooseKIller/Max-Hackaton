# Research: building on the MAX platform

Status: research notes, September 2026. Verify against the official docs before the
deadline — the brief warns that MAX documentation changes and tells us not to trust
third-party examples.

Official docs: <https://dev.max.ru/docs>

---

## 1. What MAX gives us

MAX ("MAX Business Platform") lets us build two things that matter here:

- **Chat bots** — either coded against the Bot API, or assembled in a no-code builder.
- **Mini apps** — normal web apps (HTML/JS/CSS) that run *inside* MAX. A mini app must
  be attached to a bot; the brief is explicit that it cannot be a standalone service
  that happens to sit next to a bot.

Supporting libraries:

- **MAX Bridge** — lets the mini app talk to the MAX client and the device: it reports
  the platform the app is running on (iOS, Android, desktop, web) so the app can adapt.
- **MAX UI** — a React component library in the MAX visual style.

Both matter to us because we picked React for the front end.

## 2. Bot API basics

| Item | Value |
|---|---|
| Base URL | `https://platform-api2.max.ru` |
| Auth | `Authorization: <access_token>` header. Token in the query string is no longer supported. |
| Updates | Webhooks via `POST /subscriptions`, or long polling via `GET /updates` |
| Send a message | `POST /messages` |
| Edit / delete | `PUT /messages` / `DELETE /messages` |
| Read one message | `GET /messages/{messageId}` |
| Rate limit | reported as ~30 requests/second on the platform API |

Known change to watch: `GET /chats` is reported as unsupported from June 2026 —
use subscriptions instead.

SDKs exist for JavaScript and Go, with an open client API. A Python SDK is mentioned by
third-party sources but we have **not** verified it against the official docs.
Since our backend is Python, plan on calling the REST API directly with `httpx` rather
than depending on an unverified SDK.

## 3. Hard requirements we must respect

From the track brief, not from us:

- MAX must be **the** environment for the product. The main user scenario has to be
  runnable inside MAX by a judge.
- The product must work in **both the mobile and the web version** of MAX.
- A mini app must be served over **HTTPS**.
- The bot token comes from the organizers. **Never commit it.** The brief says secrets
  in the repo, and the evaluation criteria repeat it.
- A bot's username cannot be changed after creation. Pick it carefully, once.
- Having our own API gives **no extra points by itself**. Build one only if the product
  needs it.

Worth noting: since August 2025, publishing bots and mini apps on MAX is restricted to
verified Russian legal entities. For the hackathon this is handled by the organizers
issuing us a token, but it is a real constraint for any talk of launching afterwards —
the pilot section of our presentation should name a host organization.

## 4. Chat or mini app? The brief's own rule

The brief gives a split we should follow rather than invent our own.

**Use the chat bot when the user:**
- answers a few questions in sequence
- picks from a small set of options
- gets a personal result or recommendation
- checks a status
- receives a reminder or notification
- does a short action regularly

**Use a mini app when the user needs to:**
- fill in a more complex form
- work with many parameters at once
- compare several items
- browse a list or catalog
- come back to data they entered earlier
- see several related things on one screen
- work with a rich visual interface

### How this maps to our product

| Job | Belongs in | Why |
|---|---|---|
| Onboarding, taste quiz | bot | a short sequence of questions with few options |
| "What should I do this weekend?" — top 3 picks | bot | a personal recommendation |
| "Your card expires in N days, 3,200 RUB left" | bot | a reminder, the thing chat is best at |
| Browsing the full Kazan catalog with filters | mini app | a list with many parameters |
| Comparing two events side by side | mini app | several related things on one screen |
| Planning how to spend the remaining balance | mini app | many parameters, revisited over time |
| Map of venues near me | mini app | rich visual interface |

This split is also the honest argument for building both: the *core* loop (ask → get a
pick → get reminded) is genuinely a chat job, and the *planning* surface is genuinely
not.

## 5. The platform bonus

There is a **+0.15 bonus** on the online stage, awarded all-or-nothing. To qualify:

- the main scenario must fully work and be checkable, **and**
- we must use a MAX capability beyond the minimum required, **and**
- that capability must create real user value, be naturally part of the product, work
  end to end, and be described in our materials.

Explicitly *not* enough: having our own API, having more features, or using the basic
required capabilities.

So the bonus is not "add a mini app." It is "use something in MAX that makes the product
genuinely better." Candidates to evaluate once we know the platform's surface:
proactive notifications for the expiry reminder, MAX Bridge platform adaptation,
sharing a plan into a chat with friends. To be decided after reading the full docs.

## 6. What to verify before we build

1. Read `dev.max.ru/docs` end to end, including the changelog. Do not rely on this file.
2. Confirm how a **button opens a mini app** from a chat message — this is the seam
   between our two halves and the docs excerpt we read did not cover it.
3. Confirm whether a bot can send **proactive** messages (not only replies). Our whole
   reminder feature depends on this.
4. Confirm what user identity a mini app receives via MAX Bridge, and how we tie a mini
   app session to a bot user.
5. Confirm the HTTPS/hosting requirements for the mini app so we know what we need
   running during judging.

## Sources

- [MAX developer documentation](https://dev.max.ru/docs)
- [MAX Bot API reference](https://dev.max.ru/docs-api)
- [MAX restricts bot publishing to verified RU legal entities (Habr, 2025)](https://habr.com/ru/articles/951326/)
- Track brief: [docs/brief/brief-ru.md](../brief/brief-ru.md)
