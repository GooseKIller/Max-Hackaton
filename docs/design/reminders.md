# Reminders: the one proactive message

Design note. Status: implemented (`app/reminders.py`, `app/reminder_worker.py`,
schema in `app/db.py`, tests in `app/tests/test_reminders.py`). Live MAX delivery still
to be checked with the team's token.

The money on a Pushkin Card expires on 31 December. A person who set the bot up in
September will have forgotten it by December — which is precisely when it matters. One
opt-in reminder closes that gap. It is also the cleanest fit for the MAX **+0.15**
platform bonus: a capability beyond the minimum, opt-in, on a schedule, ending in
actions the person can take.

This note explains three decisions; the code is the source of truth for the rest.

## 1. It is off until asked for — and that is the tone position, not a default

An unsolicited "your money is expiring" message is the exact pressure
[tone.md](tone.md) Rule 5 tells us to avoid, aimed at the age band most sensitive to it.
So `reminder_prefs.opted_in` starts at 0 and only an explicit choice sets it. The
scheduler sends to opted-in users and no one else.

Wiring the opt-in is a two-line job for the dialog owner, kept deliberately small so it
does not collide with the bot flow:

- Offer it once (e.g. after the first plan) with two buttons whose payloads are
  `reminders.OPT_IN_PAYLOAD` / `OPT_OUT_PAYLOAD`.
- On those payloads call `store.set_reminder_opt_in(user_id, True|False)`.

Opt-out is the same call with `False`; there is nothing else to undo.

## 2. The copy states a fact and offers options — never pressure

Per tone.md Rule 5: no exclamation marks, no countdown, no «успей». The reminder gives
a real number of days (urgent enough on its own) and two actions. It never asserts the
balance as verified — we only ever had the number the person typed, with the date they
typed it, so we repeat exactly that and ask them to check:

> Лимит Пушкинской карты сгорает 31 декабря — это 30 дней. 15.11 ты называл остаток
> 3000 ₽ — проверь его и посмотри, что рядом под эту сумму.
> [Обновить остаток] [Показать наборы]

If we have no balance for them, we say nothing about a number we do not have. The
day count is pluralised (день/дня/дней) so it never reads "осталось 3 дней".

`Показать наборы` is a callback today; once the mini-app URL is registered it should
become an `open_app` button, which is the one change needed to complete the
"reminder → recalculated plans" leg of the bonus chain.

## 3. Once per band, and crash-safe

**Bands, not thresholds.** Three windows of days-until-expiry — d30 (15–30), d14 (4–14),
d3 (0–3). A person who opts in late gets only the reminders whose window they are still
in, not all the earlier ones fired at once. A full year yields at most three sends.

**De-duplication that survives a crash.** `reminders_sent` has one row per
`(user_id, year, rule_key)` with a `status`:

1. `claim_reminder` takes the slot — an `INSERT OR IGNORE` for a fresh one, or an
   `UPDATE` that reclaims a slot stuck in `sending` older than 10 minutes.
2. Send.
3. `mark_reminder_sent` sets `status='sent'` only after a successful send.

A crash between the send and the mark leaves a `sending` row, which a later pass
reclaims and retries — so a reminder is retried, not silently dropped. The one residual
risk is a send that succeeded but crashed before the mark: it may be re-sent once after
the grace period. For an opt-in reminder that is an acceptable, documented trade rather
than a lost message. `UNIQUE(user_id, year, rule_key)` means the scheduler can run as
often as it likes.

## Running it

Its own process, on purpose — testable and demonstrable without touching the MAX receive
code the bot owner maintains:

```bash
python -m app.reminder_worker --once            # one pass
python -m app.reminder_worker --loop            # hourly
python -m app.reminder_worker --once --dry-run  # print instead of send (no token)
```

Delivery goes to the MAX REST API by `user_id`, reusing the app's token and the Russian
Trusted Root via `config.ssl_context()`. It does not import the bot's `MaxClient`, to
stay isolated while MAX integration is hardened; the two can later share one HTTP client
if the team prefers.

## What is deliberately not here

- No opt-in UI in the dialog yet — a two-line call for the bot owner (above), left to
  them to avoid colliding with the flow they own.
- No `open_app` deep link until the mini-app URL exists.
- Moscow time is a fixed UTC+3 (correct for Russia, no tz database needed). Revisit only
  if the pilot ever spans a DST-observing zone.
