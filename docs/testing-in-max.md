# How we test the bot in MAX

Checked 24 September 2026 against the official MAX docs. The brief warns that MAX
documentation changes and that third-party guides go stale — re-check before
submission.

## Short answer

**We cannot create a bot as private individuals.** The official docs are explicit:
bot creation requires a verified Russian legal entity, individual entrepreneur, or
self-employed person. "Individual consumers cannot create bots on MAX."

For the hackathon this is already solved — the brief, [brief-ru.md:449](brief/brief-ru.md):

> «В рамках проведения хакатона токен чат-бота предоставляется организаторами.»

So the practical answer is: **get the token from the organizers.** That is the
intended route and it should be chased now, not on deadline night.

Until it arrives, `backend/console.py` runs the entire conversation locally, and none
of that work is wasted — the dialog is transport-agnostic.

## The three routes to a token, ranked

### 1. The organizers' token — primary

Nothing to do but ask for it. This is what the brief promises. It also avoids the
moderation queue entirely.

**Action: find out from the organizers when and how it is handed over.** If it only
appears at the offline stage, that changes our plan, so ask early.

### 2. A self-employed profile — viable backup

Since **15 June 2026** the MAX partner platform is open to self-employed people
registered in Russia. A self-employed profile may create **2 bots** (organizations and
IPs get 5).

Steps, per the docs and a practitioner write-up:

1. `business.max.ru`, authorise by phone.
2. Choose the "self-employed" profile type.
3. Verify through Gosuslugi.
4. Create the bot: logo, name, nickname, description.
5. It goes to moderation — **up to 48 hours on business days.**
6. **The token is issued only after moderation passes.**

Two things to note. The nickname is auto-generated from the profile
(`se(orgid)_bot` for self-employed, `idИНН_bot` for organizations), so the
"pick the username carefully, it cannot be changed" worry may not even apply on this
route. And 48 business hours is real time we do not have much of — if anyone on the
team is already self-employed, starting this today costs nothing and buys insurance.

### 3. Waiting and hoping — not a route

With roughly a week left, the moderation queue plus the unknown handover date means we
should not have a single point of failure here.

## What we can test, and when

| What | Needs | Status |
|---|---|---|
| The whole conversation, wording, filters | nothing | ✅ `backend/console.py` |
| Update parsing and the webhook path | nothing | ✅ smoke-tested with a synthetic MAX payload |
| That the token is valid | a token | `backend/check_token.py` |
| The bot live in MAX, from a phone | a token | `backend/runner.py` — **no public HTTPS needed** |
| The webhook in production | token + public HTTPS | `docker compose up`, plus hosting |
| A mini app | token + public HTTPS | not started; scope still open |

### The useful part: long polling needs no hosting

`GET /updates` is long polling, so the bot can run **from a laptop** and still be a
real bot in MAX that a judge could message. No tunnel, no deployment, no certificate.

That means the day the token arrives we can be talking to the bot on a phone within
minutes:

```bash
cp .env.example .env          # put MAX_BOT_TOKEN in it
python3 backend/check_token.py   # confirm the token works at all
python3 backend/runner.py        # the bot is now live in MAX
```

`check_token.py` calls `GET /me`, which returns the bot's `user_id`, `username` and
`is_bot`. Run it first — it separates "the token is wrong" from "our code is wrong".

### When we do need public HTTPS

- **Webhooks** (`POST /subscriptions`) for the deployed version.
- **A mini app**, which must be served over HTTPS to attach to a bot.

For development, a tunnel (cloudflared, ngrok) is enough. For judging we need
something stable for the whole review window — the brief requires the bot to stay
reachable, and containerisation explicitly does not replace a live product in MAX.

## Open questions to resolve with the organizers

1. **When is the token handed over?** Everything above depends on this date.
2. **Is the bot pre-created and moderated by them**, or do we submit it for moderation
   ourselves? If the latter, the 48-hour window has to be planned around.
3. **Can the bot's display name and description be set by us** after handover?
4. **Is there hosting for the mini app**, or do we arrange HTTPS ourselves?

## Things that are still unverified in our code

Written from the docs, never run against a live token. All isolated in
`backend/app/max_client.py` so the blast radius is one file:

- the **inline keyboard payload shape** for suggested replies,
- the exact `GET /updates` parameters (`marker`, `timeout`),
- the update envelope for a **button press** versus a plain message,
- whether a bot can send **proactive** messages — the expiry reminder depends on it.

The first hour with a real token should go to these four, in that order.

## Sources

- [Creating and moderating a chat bot, MAX docs](https://dev.max.ru/docs/chatbots/bots-create/create)
- [MAX Bot API reference](https://dev.max.ru/docs-api)
- [The MAX partner platform opened to self-employed people, VK](https://vk.company/ru/press/releases/12335/)
- [Launching a bot in MAX as a self-employed person, Habr](https://habr.com/ru/articles/1048650/)
- [MAX restricts bot creation and publishing to verified RU entities, Habr](https://habr.com/ru/articles/951326/)
