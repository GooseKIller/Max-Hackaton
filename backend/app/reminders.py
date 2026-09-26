"""
Reminders: the one proactive message we send, and the rules that keep it from
becoming pressure.

Why this exists
---------------
The money on a Pushkin Card expires on 31 December and does not roll over. The whole
product is about not losing it — but a person who set the bot up in September will have
forgotten it by December, which is exactly when it matters. A reminder closes that gap.

It is also the clearest fit for the MAX "+0.15" platform bonus: a capability beyond the
minimum, opt-in, delivered on a schedule, ending in the pieces the person can act on.

The tone constraint (see docs/design/tone.md, Rule 5)
-----------------------------------------------------
A reminder is the single easiest place to break tone. "Твои деньги сгорят!!!" is a
reactance trigger for exactly our age band and reads as a tactic. So:

- The reminder is **off until the person turns it on.** No unsolicited "you're losing
  money" message ever.
- The copy states a fact and offers options. No exclamation marks, no countdown, no
  "успей". The fact (a real number of days) is urgent enough on its own; delivering it
  flatly is what makes it credible.
- We never assert the balance as verified. We only ever had the number the person told
  us, with the date they told us — so we say exactly that and ask them to check.

Design of the once-per-band schedule and the crash-safe de-duplication is in
docs/design/reminders.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from .config import BALANCE_EXPIRES
from .db import Store

# Moscow is UTC+3 all year (no DST in Russia), so a fixed offset is correct and needs
# no tz database. days_left is computed here so "68 days" means the same thing to the
# scheduler and to the copy.
MSK = timezone(timedelta(hours=3))

# Callback payloads the dialog routes to set_reminder_opt_in. Kept here so the two
# sides agree on one spelling.
OPT_IN_PAYLOAD = "reminders:on"
OPT_OUT_PAYLOAD = "reminders:off"

# A reminder is stuck if it claimed the slot but never reported delivery within this
# window — a crash between send and mark. After it, another pass may retry.
STALE_AFTER = timedelta(minutes=10)

# Each rule fires once, inside a band of days-until-expiry. Bands (not "<= N") so a
# person who opts in late only gets the reminders whose window they are still in,
# not all of the earlier ones at once.
RULE_BANDS: list[tuple[str, int, int]] = [
    ("d30", 15, 30),   # "about a month left"
    ("d14", 4, 14),    # "a couple of weeks"
    ("d3", 0, 3),      # "the last few days"
]


def _expiry() -> date:
    return date.fromisoformat(BALANCE_EXPIRES)


def days_left(now: datetime | None = None) -> int:
    """Whole days from today (Moscow) to the expiry date. 0 on the day itself."""
    today = (now.astimezone(MSK) if now else datetime.now(MSK)).date()
    return (_expiry() - today).days


def rule_for(days: int) -> str | None:
    """The single reminder band the current days-left falls in, or None."""
    for key, lo, hi in RULE_BANDS:
        if lo <= days <= hi:
            return key
    return None


def _plural_days(n: int) -> str:
    """день / дня / дней — so the copy never reads 'осталось 3 дней'."""
    if 11 <= n % 100 <= 14:
        return "дней"
    last = n % 10
    if last == 1:
        return "день"
    if 2 <= last <= 4:
        return "дня"
    return "дней"


def _report_date_ru(reported_at: str | None) -> str | None:
    """The date the person last told us their balance, as DD.MM."""
    if not reported_at:
        return None
    try:
        reported = datetime.fromisoformat(reported_at)
        if reported.tzinfo is None:
            reported = reported.replace(tzinfo=MSK)
        return reported.astimezone(MSK).strftime("%d.%m")
    except ValueError:
        return None


@dataclass(frozen=True)
class Reminder:
    """A rendered reminder, ready to hand to a sender."""

    user_id: str
    rule_key: str
    text: str
    buttons: list[str]


def render(
    user_id: str,
    rule_key: str,
    days: int,
    balance_general: int | None,
    balance_reported_at: str | None,
) -> Reminder:
    """
    Build the message. Fact first, options after — never pressure.

    If we have a balance the person told us, we repeat it *with its date* and ask them
    to check it, because we cannot verify it. If we do not, we say nothing about a
    number we do not have.
    """
    days_phrase = f"{days} {_plural_days(days)}"
    reported = _report_date_ru(balance_reported_at)

    if balance_general is not None and reported is not None:
        text = (
            f"Лимит Пушкинской карты сгорает 31 декабря — это {days_phrase}. "
            f"{reported} ты называл остаток {balance_general} ₽ — проверь его "
            f"и посмотри события в Казани под эту сумму."
        )
    elif balance_general is not None:
        text = (
            f"Лимит Пушкинской карты сгорает 31 декабря — это {days_phrase}. "
            f"Ты называл остаток {balance_general} ₽ — проверь его и посмотри, "
            f"события в Казани под эту сумму."
        )
    else:
        text = (
            f"Лимит Пушкинской карты сгорает 31 декабря — это {days_phrase}. "
            f"Проверь остаток и посмотри события в Казани."
        )

    return Reminder(
        user_id=user_id,
        rule_key=rule_key,
        text=text,
        buttons=["Обновить остаток", "Показать наборы", "Отключить напоминания"],
    )


def due(store: Store, now: datetime | None = None) -> list[Reminder]:
    """
    Everyone who should get a reminder in this pass: opted in, in a band, and not
    already sent that band this year. De-duplication happens at claim time, so a
    row here is a candidate, not a guarantee.
    """
    now = now or datetime.now(MSK)
    days = days_left(now)
    rule = rule_for(days)
    if rule is None or not 10 <= now.astimezone(MSK).hour < 21:
        return []

    year = now.astimezone(MSK).year
    out: list[Reminder] = []
    for user_id in store.opted_in_user_ids():
        # Skip only what is already delivered. A row still in 'sending' (a previous
        # send that failed) stays a candidate; claim_reminder decides whether it is
        # stale enough to retry, so a failed delivery is picked up, not lost.
        if store.reminder_status(user_id, year, rule) == "sent":
            continue
        profile = store.load_profile(user_id)
        if profile is None or profile.age is None or profile.balance_general == 0:
            continue
        out.append(
            render(
                user_id,
                rule,
                days,
                profile.balance_general if profile else None,
                profile.balance_reported_at if profile else None,
            )
        )
    return out


def run_once(store: Store, send, now: datetime | None = None) -> dict:
    """
    One scheduler pass. `send(reminder) -> bool` does the actual delivery and returns
    whether it succeeded; keeping it injectable means this whole module is testable
    without a network and without touching the MAX client.

    For each candidate: claim the slot, send, and only then mark it delivered. A
    failed send leaves the slot 'sending', which a later pass reclaims once it is
    stale — so a reminder is retried, never silently dropped or sent twice in the
    same pass.
    """
    now = now or datetime.now(MSK)
    year = now.astimezone(MSK).year
    utc_now = now.astimezone(timezone.utc)
    stale_before = (utc_now - STALE_AFTER).isoformat(timespec="seconds")

    sent = failed = 0
    for reminder in due(store, now):
        if not store.claim_reminder(
            reminder.user_id, year, reminder.rule_key, stale_before,
            claimed_at=utc_now.isoformat(timespec="seconds"),
        ):
            continue  # someone else owns it, or it is not stale yet
        # Recheck consent immediately before handing the message to the sender.
        if not store.is_opted_in(reminder.user_id):
            continue
        try:
            delivered = send(reminder)
        except Exception:
            delivered = False
        if delivered:
            store.mark_reminder_sent(reminder.user_id, year, reminder.rule_key)
            sent += 1
        else:
            failed += 1  # left 'sending'; a later pass retries after STALE_AFTER
    return {"sent": sent, "failed": failed}
