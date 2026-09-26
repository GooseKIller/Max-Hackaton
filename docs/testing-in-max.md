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

## TLS: the Russian Trusted Root CA

**If your first call to MAX dies with `CERTIFICATE_VERIFY_FAILED`, this is why.**

`platform-api2.max.ru` presents a certificate chained to *"The Ministry of Digital
Development and Communications — Russian Trusted Root CA"*. That root is in neither
`certifi` nor the default macOS/Linux trust stores. Browsers in Russia usually have
it preinstalled, which is exactly why the API looks fine in a browser and fails in
code.

Verified locally:

```
issuer=C=RU, O=The Ministry of Digital Development and Communications,
       CN=Russian Trusted Sub CA
subject=CN=*.max.ru, O=MAX LLC
Verify return code: 20 (unable to get local issuer certificate)   # without the root
Verify return code: 0 (ok)                                        # with it
```

Handled in the repo: the root is committed at
`certs/russian-trusted-root-ca.pem` (a public government root certificate, safe to
commit; SHA-256 `D2:6D:2D:02:31:B7:C3:9F:92:CC:73:85:12:BA:54:10:35:19:E4:40:5D:68:B5:BD:70:3E:97:88:CA:8E:CF:31`,
valid to 2032-02-27), and `backend/app/config.py:ssl_context()` **adds** it to the
normal public bundle. Every outbound client uses that context.

It adds one root; it does not replace the bundle and it does not disable
verification. `verify=False` would also have silenced the error, and would also have
made the connection unauthenticated — not a trade worth making for a client carrying
a bot token.

The Dockerfile copies `certs/` for the same reason; a slim image has no more idea
about this root than a laptop does.

## Verified against a live token

Checked 26 September 2026 with the organizers' token.

| Question | Answer |
|---|---|
| `GET /me` | **works** — `@t179_hakaton_max_bot`, id 417224539, `is_bot: true` |
| `GET /updates` long polling | **works** — HTTP 200, returns a `marker` |
| Does the `.env` file get read? | It does **now**. It did not before — see below. |
| Keyboard payload shape | still unverified — needs someone to message the bot |
| Update shape for a button press | still unverified — same |
| Proactive sends | **still unverified, and still the most important open question** |

To finish the list, message the bot from MAX, then:

```bash
python3 backend/probe_max.py --wait 30      # prints the chat id and the raw update
python3 backend/probe_max.py --chat <id>    # sending, keyboards, proactive
```

### A trap worth knowing about

`.env` was documented everywhere as the place to put the token, and nothing loaded
it: `os.getenv` reads the process environment, and only Docker Compose was reading
`env_file` on its own. So every local command reported "MAX_BOT_TOKEN is not set" at
someone who had just set it. `config.py` now loads `.env` itself, and a real
environment variable still wins over the file.

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
