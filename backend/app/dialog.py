"""
The conversation.

Transport-agnostic on purpose: this module takes text in and returns text plus
buttons out, and knows nothing about MAX. That means we can run the whole thing in
a terminal today, without a bot token, and plug MAX in later without touching any
of the logic here.

Register rules from docs/design/tone.md apply to every string in this file:
no forced slang or pressure. State the fact, give options and explain the actual
inputs used by a recommendation. These are design choices to validate with users.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum, auto
import re
from zoneinfo import ZoneInfo

from .catalog import EventSource
from .db import Store
from .config import BALANCE_EXPIRES, CARD_RULES_2026, ELIGIBLE_AGE_MAX, ELIGIBLE_AGE_MIN
from .filters import candidates, km_between
from .labeling import label_all
from .models import Event, Seance, UserProfile
from .photos import PhotoBook
from .plans import build_plans
from .timing import Timing, baseline as latency_baseline, weight as timing_weight
from .taste import MOOD_TARGETS, Ranker, Scored, Taste, mood_match, quiz_cards

WEEKDAYS_RU = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")
MONTHS_RU = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)

QUIZ_LENGTH = 5

# The shape of the conversation. Bump this whenever a step is added, removed or
# repurposed. A stored position from an older shape means nothing — resuming into
# it drops the user into a path that no longer exists, which is how a returning
# user ended up in the removed three-events-at-once view after the feed shipped.
# Profile and taste survive a bump; only the position is discarded.
FLOW_VERSION = 2

# Emoji as field markers, not as personality.
#
# tone.md rule 2 rules out emoji doing emotional labour — a bot performing
# enthusiasm at a 16-year-old. A marker that says "this line is the price" is a
# different thing: it is an icon, and in a messenger it is what makes a card
# scannable instead of a paragraph. One per line, never inside a sentence, never
# to convey feeling.
CATEGORY_ICON = {
    "spektakli": "🎭",
    "koncerty": "🎵",
    "vystavki": "🖼",
    "ekskursii": "🚶",
    "obuchenie": "✍️",
    "vstrechi": "💬",
    "prazdniki": "🎉",
    "kino": "🎬",
    "prochie": "✨",
}

# The catalogue's category is not always the obvious one — a show titled
# «Спектакль …» can be filed under `prochie`. The title is the stronger signal
# for an icon, so it wins.
TITLE_ICON = (
    ("спектакл", "🎭"),
    ("мюзикл", "🎭"),
    ("бэби-спектакл", "🎭"),
    ("концерт", "🎵"),
    ("органн", "🎵"),
    ("квартирник", "🎵"),
    ("выставк", "🖼"),
    ("экскурси", "🚶"),
    ("мастер-класс", "✍️"),
    ("воркшоп", "✍️"),
    ("лаборатори", "✍️"),
    ("лекци", "💬"),
    ("интеллектуальная игра", "🧠"),
    ("квиз", "🧠"),
    ("показ фильма", "🎬"),
    ("кинопоказ", "🎬"),
    ("документальное кино", "🎬"),
)


def _icon(event: Event) -> str:
    title = event.name.lower()
    for needle, icon in TITLE_ICON:
        if needle in title:
            return icon
    return CATEGORY_ICON.get(event.category, "✨")


# Why an event was picked, in plain words. Keyed by the strongest score component.
REASON_TEXT = {
    "taste": "похоже на то, что ты отметил(а)",
    "discovery": "необычный формат, такого мало в афише",
    "budget": "хорошо ложится в остаток",
    "convenience": "подходит под выбранное время",
    "urgency": "успеваешь до конца года",
}


class Step(Enum):
    NEW = auto()
    ASK_AGE = auto()
    ASK_BALANCE = auto()
    ASK_CINEMA = auto()
    EDIT_BALANCE = auto()
    EDIT_CINEMA = auto()
    ASK_TIME = auto()
    ASK_MOOD = auto()
    QUIZ = auto()
    SWIPE = auto()
    READY = auto()


@dataclass
class Reply:
    """What the bot says back. `buttons` are suggested answers, not a keyboard spec."""

    text: str
    buttons: list[str] = field(default_factory=list)
    # MAX fetches this server-side; delivery is best-effort and falls back to text.
    image_url: str | None = None


@dataclass
class Session:
    profile: UserProfile
    taste: Taste = field(default_factory=Taste)
    step: Step = Step.NEW
    offset: int = 0
    quiz: list[Event] = field(default_factory=list)
    quiz_at: int = 0
    swiped: int = 0
    # Titles already shown. Event ids are not enough: the same production runs many
    # times and exists as several records, so an id-only guard shows it again.
    seen_titles: set[str] = field(default_factory=set)
    # When our last message went out, so the next answer can be timed.
    last_sent_at: datetime | None = None
    last_timing: Timing | None = None
    # This person's own recent answering times, so "fast" and "slow" can mean fast
    # and slow for them rather than against a fixed number.
    latencies: list[int] = field(default_factory=list)
    mood: str | None = None
    last_shown: list[Scored] = field(default_factory=list)


def _fmt_when(seance: Seance) -> str:
    d = seance.start
    return f"{WEEKDAYS_RU[d.weekday()]} {d.day} {MONTHS_RU[d.month - 1]}, {d:%H:%M}"


def _days_left(today: date | None = None) -> int:
    today = today or date.today()
    return max(0, (date.fromisoformat(BALANCE_EXPIRES) - today).days)


def _fmt_expiry() -> str:
    d = date.fromisoformat(BALANCE_EXPIRES)
    return f"{d.day} {MONTHS_RU[d.month - 1]}"


def _parse_int(text: str) -> int | None:
    # Do not silently turn '-500', '12.5', '1000–2500' or '500 и 200' into money.
    value = text.strip().lower()
    if not re.fullmatch(r"(?:[0-9]{1,5}|[0-9]{1,2}(?:[ \u00a0\u202f][0-9]{3}))(?:\s*(?:₽|руб\.?))?", value):
        return None
    return int(re.sub(r"[^0-9]", "", value))


class Dialog:
    """
    One bot, many sessions.

    Sessions are cached in memory and rehydrated when a Store is supplied.
    """

    def __init__(self, source: EventSource, store: Store | None = None):
        self._source = source
        self._store = store
        self._events = source.all_events()
        self._by_id = {e.id: e for e in self._events}
        self._labels = label_all(self._events)
        self._photos = PhotoBook()
        self._ranker = Ranker(self._events, self._labels)
        self._sessions: dict[str, Session] = {}

        if store is not None:
            store.save_labels([l.as_dict() for l in self._labels.values()])

    # -- sessions ------------------------------------------------------------

    def _session(self, user_id: str) -> Session:
        if user_id in self._sessions:
            return self._sessions[user_id]

        session = Session(profile=UserProfile(user_id=user_id))
        if self._store is not None:
            # Rehydrate: a restart should not drop someone mid-onboarding, and a
            # taste built over several conversations is the whole point of storing it.
            profile = self._store.load_profile(user_id)
            if profile is not None:
                session.profile = profile
                session.taste = self._store.load_taste(user_id)
            session.latencies = self._store.recent_latencies(user_id)
            saved = self._store.load_session(user_id)
            if saved and saved.get("flow_version") != FLOW_VERSION:
                # Keep who they are and what they like; drop where they were.
                session.step = (
                    Step.SWIPE if session.profile.is_onboarded else Step.NEW
                )
                saved = None
            if saved:
                try:
                    session.step = Step[saved["step"]]
                except KeyError:
                    session.step = Step.NEW
                session.offset = saved["list_offset"]
                session.mood = saved["mood"]
                # Mood lives in the session, not in the stored taste vector, so it
                # has to be re-applied as an overlay when a session is rehydrated.
                session.taste.set_mood(session.mood)
                session.quiz = [
                    self._by_id[i] for i in saved["quiz_ids"] if i in self._by_id
                ]
                session.quiz_at = saved["quiz_at"]
                # A quiz whose events have aged out of the catalogue cannot resume.
                if session.step is Step.QUIZ and session.quiz_at >= len(session.quiz):
                    session.step = Step.READY

        self._sessions[user_id] = session
        return session

    def _persist(self, session: Session) -> None:
        if self._store is None:
            return
        uid = session.profile.user_id
        self._store.save_profile(session.profile)
        self._store.save_taste(uid, session.taste)
        self._store.save_session(
            uid,
            step=session.step.name,
            list_offset=session.offset,
            mood=session.mood,
            quiz_ids=[e.id for e in session.quiz],
            quiz_at=session.quiz_at,
            flow_version=FLOW_VERSION,
        )

    def reset(self, user_id: str) -> None:
        self._sessions.pop(user_id, None)

    # -- routing -------------------------------------------------------------

    def handle(self, user_id: str, text: str, now: datetime | None = None) -> Reply:
        now = now or datetime.now(ZoneInfo("Europe/Moscow")).replace(tzinfo=None)
        text = (text or "").strip()
        session = self._session(user_id)

        # How long they took to answer our last card. This is the closest thing a
        # chat bot has to dwell time; see timing.py for what we read into it.
        latency = None
        if session.last_sent_at is not None:
            latency = int((now - session.last_sent_at).total_seconds() * 1000)
            if latency < 0:
                latency = None
        if latency is not None:
            session.latencies.append(latency)
            del session.latencies[:-40]
        session.last_timing = Timing(
            latency_ms=latency,
            position=session.swiped,
            baseline_ms=latency_baseline(session.latencies),
        )

        if text.lower() in ("/start", "начать", "заново", "/reset"):
            self.reset(user_id)
            session = self._session(user_id)
            reply = self._greet(session)
            self._persist(session)
            return reply

        handlers = {
            Step.NEW: lambda: self._greet(session),
            Step.ASK_AGE: lambda: self._take_age(session, text),
            Step.ASK_BALANCE: lambda: self._take_balance(session, text, now),
            Step.ASK_CINEMA: lambda: self._take_cinema(session, text, now),
            Step.EDIT_BALANCE: lambda: self._take_balance(session, text, now, editing=True),
            Step.EDIT_CINEMA: lambda: self._take_cinema(session, text, now, editing=True),
            Step.ASK_TIME: lambda: self._take_time(session, text, now),
            Step.ASK_MOOD: lambda: self._take_mood(session, text, now),
            Step.QUIZ: lambda: self._take_quiz(session, text, now),
            Step.SWIPE: lambda: self._take_swipe(session, text, now),
            Step.READY: lambda: self._take_command(session, text, now),
        }
        reply = handlers[session.step]()
        session.last_sent_at = now
        self._persist(session)
        return reply

    # -- onboarding ----------------------------------------------------------

    def _greet(self, session: Session) -> Reply:
        note = ""
        if self._source.is_synthetic:
            note = (
                "\n\nСейчас работаю на тестовых данных: события сгенерированы, "
                "ссылки на покупку нерабочие."
            )
        session.step = Step.ASK_AGE
        return Reply(
            text=(
                "Помогу выбрать, на что потратить Пушкинскую карту в Казани.\n"
                "Несколько вопросов, потом покажу варианты.\n\n"
                "Сколько тебе лет?" + note
            ),
            buttons=["14", "16", "18", "20"],
        )

    def _take_age(self, session: Session, text: str) -> Reply:
        age = _parse_int(text)
        if age is None or not (ELIGIBLE_AGE_MIN <= age <= ELIGIBLE_AGE_MAX):
            return Reply(
                text=(
                    f"Пушкинская карта работает с {ELIGIBLE_AGE_MIN} до "
                    f"{ELIGIBLE_AGE_MAX} лет. Сколько тебе?"
                ),
                buttons=["14", "16", "18", "20"],
            )
        session.profile.age = age
        session.step = Step.ASK_BALANCE
        r = CARD_RULES_2026
        return Reply(
            text=(
                "Сколько осталось на карте?\n\n"
                "Напиши число — например, 4226.\n"
                "Точная сумма есть в «Госуслуги Культура»."
            ),
            # Two buttons, not four. A row of round numbers reads as "pick one of
            # these", and the invitation to type your own was drowning in the third
            # line of a four-line message. Most balances are not round.
            buttons=["не знаю"],
        )

    def _take_balance(self, session: Session, text: str, now: datetime, editing: bool = False) -> Reply:
        r = CARD_RULES_2026
        if text.lower() in ("не знаю", "хз", "?"):
            session.profile.balance_general = None
            session.profile.balance_cinema = None
            session.profile.balance_reported_at = None
            return self._after_balance(session, now, editing, "Пока покажу события без кино. Для расчёта плана понадобится точный остаток.\n\n")
        else:
            amount = _parse_int(text)
            if amount is None or amount < 0 or amount > r.total:
                return Reply(
                    text=f"Введи число от 0 до {r.total}.",
                    buttons=["5000", "3200", "1500", "не знаю"],
                )
            session.profile.balance_general = amount
            session.profile.balance_cinema = None
            session.profile.balance_reported_at = now.isoformat(timespec="seconds")

        if amount == 0:
            session.profile.balance_cinema = 0
            return self._after_balance(session, now, editing)
        if editing:
            session.step = Step.EDIT_CINEMA
            return Reply(
                text=("Сколько из остатка ещё можно потратить на кино?\n"
                      "Если не знаешь, подберу события без кино."),
                buttons=["0", str(min(amount, r.cinema_cap)), "без кино"],
            )

        # Cinema has its own sub-limit, but asking about it before the user has
        # seen anything costs a step and buys nothing: cinema is a small slice of
        # what we show. Start without it and ask when a plan actually needs it.
        session.profile.balance_cinema = None
        return self._after_balance(session, now, editing=False)

    def _take_cinema(self, session: Session, text: str, now: datetime, editing: bool = False) -> Reply:
        limit = min(session.profile.balance_general or 0, CARD_RULES_2026.cinema_cap)
        if text.lower() in ("не знаю", "без кино", "пропустить"):
            session.profile.balance_cinema = None
        else:
            amount = _parse_int(text)
            if amount is None or not 0 <= amount <= limit:
                return Reply(text=f"Введи остаток на кино от 0 до {limit} ₽ или выбери «без кино».", buttons=["0", "без кино"])
            session.profile.balance_cinema = amount
        return self._after_balance(session, now, editing)

    def _after_balance(self, session: Session, now: datetime, editing: bool, note: str = "") -> Reply:
        session.offset = 0
        if editing:
            session.step = Step.READY
            return self._recommend(session, now, preamble=note or None)
        # Straight into the feed. The old flow asked about time and mood and then
        # ran a five-card quiz — eleven steps and 2332 characters before the user
        # saw a single event, against a rule of thumb of five to seven steps to
        # first value. Time, mood and the cinema sub-limit are refinements now:
        # they are offered once there is something on screen to refine.
        session.step = Step.SWIPE
        session.swiped = 0
        return self._swipe(session, now, preamble=note + "Смотри, что есть. Листай:")

    def _take_time(self, session: Session, text: str, now: datetime) -> Reply:
        t = text.lower()
        only = "только" in t
        session.profile.free_weekends = not (only and "вечер" in t)
        session.profile.free_evenings = not (only and "выходн" in t)

        session.step = Step.SWIPE
        return self._swipe(session, now, preamble="Обновил. Дальше:")

    def _take_mood(self, session: Session, text: str, now: datetime) -> Reply:
        # Mood, not momentary emotion: it is stable over a session and, per the
        # affective-recommender literature, it is what helps in cold start.
        matched = next((m for m in MOOD_TARGETS if m.lower() == text.lower()), None)
        if matched:
            session.mood = matched
            session.taste.set_mood(matched)

        session.step = Step.SWIPE
        return self._swipe(session, now, preamble="Обновил. Дальше:")

    def _log(
        self, session: Session, event_id: int, signal: str,
        surface: str | None = None, position: int | None = None,
    ) -> None:
        if self._store is None:
            return
        t = session.last_timing
        self._store.log(
            session.profile.user_id, event_id, signal,
            surface=surface, position=position, mood=session.mood,
            latency_ms=t.latency_ms if t else None,
        )

    def _swipe(
        self, session: Session, now: datetime, preamble: str = ""
    ) -> Reply:
        """
        One event, one picture, one decision.

        This is the product, not a questionnaire in front of it. Every card is a
        real thing the user could go to tonight, so a swipe is both a taste signal
        and a real choice — the reason ДайВинчик's loop works at all.
        """
        found = candidates(self._events, session.profile, now)
        if not found:
            session.step = Step.READY
            return Reply(
                text="Под эти условия ничего не нашлось. Можно расширить поиск.",
                buttons=["другое время", "другой остаток", "заново"],
            )

        ranked = self._ranker.score(found, session.profile, session.taste, today=now.date())
        fresh = [
            s_ for s_ in ranked
            if s_.event.name.strip().casefold() not in session.seen_titles
        ]
        if not fresh:
            session.seen_titles.clear()
            fresh = ranked

        card = fresh[0]
        session.last_shown = [card]
        session.seen_titles.add(card.event.name.strip().casefold())
        self._log(session, card.event.id, "impression", surface="feed", position=session.swiped)

        lines = []
        if preamble:
            lines.append(preamble + "\n")
        lines.append(f"{_icon(card.event)} {card.event.name}")
        lines.append(f"💳 {card.event.price} ₽ · {_fmt_when(card.seance)}")
        lines.append(f"📍 {card.event.place.name}")
        reason = REASON_TEXT.get(card.top_reason())
        if reason and session.swiped:
            lines.append(f"\n💡 {reason}")

        buttons = ["❤️ пойду", "👎 не моё"]
        # Offered once there is enough signal for a plan to be worth anything.
        if session.swiped >= 3 and session.profile.balance_general:
            buttons.append("🗓 собрать план")

        return Reply(
            text="\n".join(lines),
            buttons=buttons,
            image_url=self._photos.for_event(card.event),
        )

    def _take_swipe(self, session: Session, text: str, now: datetime) -> Reply:
        t = text.lower().strip()
        card = session.last_shown[0] if session.last_shown else None

        if "собрать план" in t or t in ("план", "/plan"):
            return self._plans(session, now)
        if "сколько осталось" in t or t in ("баланс", "/balance"):
            return self._balance_note(session, now)
        if "другой остаток" in t or t == "/balance_set":
            session.step = Step.EDIT_BALANCE
            return Reply(text="Сколько сейчас на карте?\n\nНапиши число — например, 4226.")
        if "другое время" in t or t == "/time":
            session.step = Step.ASK_TIME
            return Reply(
                text="Когда тебе удобно ходить?",
                buttons=["вечером и в выходные", "только в выходные", "только вечером"],
            )
        if "другое настроение" in t or t == "/mood":
            session.mood = None
            session.taste.set_mood(None)
            session.step = Step.ASK_MOOD
            return Reply(text="Чего сейчас хочется?", buttons=list(MOOD_TARGETS.keys()))

        if card is not None:
            if "пойд" in t or t in ("да", "+", "интересно", "❤️"):
                session.taste.add(
                    card.vector, "like",
                    decay=timing_weight("like", session.last_timing)
                    if session.last_timing else 1.0,
                )
                self._log(session, card.event.id, "like", surface="feed", position=session.swiped)
                session.swiped += 1
                link = card.event.sale_link
                head = "Записал. Билет:" if link else "Записал."
                note = f"{head}\n{link}\n\n" if link else f"{head}\n\n"
                if self._source.is_synthetic:
                    note = "Записал. Ссылка нерабочая — каталог тестовый.\n\n"
                return self._swipe(session, now, preamble=note + "Дальше:")
            if "не мо" in t or t in ("нет", "-", "👎"):
                session.taste.add(
                    card.vector, "dislike",
                    decay=timing_weight("dislike", session.last_timing)
                    if session.last_timing else 1.0,
                )
                self._log(session, card.event.id, "dislike", surface="feed", position=session.swiped)
                session.swiped += 1
                return self._swipe(session, now)

        return self._swipe(session, now)

    def _quiz_card(self, session: Session) -> str:
        event = session.quiz[session.quiz_at]
        n = session.quiz_at + 1
        tags = ", ".join(event.tag_names[:3])
        lines = [f"{n}/{len(session.quiz)}  {event.name}"]
        if tags:
            lines.append(f"  {tags}")
        if event.short_description:
            lines.append(f"  {event.short_description}")
        return "\n".join(lines)

    def _take_quiz(self, session: Session, text: str, now: datetime) -> Reply:
        t = text.lower()
        event = session.quiz[session.quiz_at]
        vector = self._ranker.vector_for(event)

        if t.startswith("интерес") or t in ("да", "+"):
            signal = "like"
        elif t.startswith("не мо") or t in ("нет", "-"):
            signal = "dislike"
        else:
            signal = "skip"
        session.taste.add(vector, signal)
        self._log(session, event.id, signal, surface="quiz", position=session.quiz_at)

        session.quiz_at += 1
        if session.quiz_at < len(session.quiz):
            return Reply(
                text=self._quiz_card(session),
                buttons=["интересно", "не моё", "пропустить"],
            )

        session.step = Step.READY
        session.offset = 0
        return self._recommend(session, now, preamble="Понял. Вот что подходит:")

    # -- commands ------------------------------------------------------------

    def _take_command(self, session: Session, text: str, now: datetime) -> Reply:
        t = text.lower()
        if t in ("собрать план", "план", "/plan"):
            return self._plans(session, now)
        if t in ("ещё", "еще", "дальше", "/more"):
            session.offset += 3
            return self._recommend(session, now)
        if t in ("сколько осталось", "баланс", "/balance"):
            return self._balance_note(session, now)
        if t in ("другой остаток", "/balance_set"):
            session.step = Step.EDIT_BALANCE
            return Reply(text="Сколько сейчас на карте?", buttons=["5000", "3200", "1500"])
        if t in ("другое настроение", "/mood"):
            session.mood = None
            session.taste.set_mood(None)
            session.step = Step.ASK_MOOD
            return Reply(text="Чего сейчас хочется?", buttons=list(MOOD_TARGETS.keys()))

        # A typed title is not an observed ticket-link click. Only explicit UI
        # instrumentation may record buy_click; do not fabricate conversion data.
        session.offset = 0
        return self._recommend(session, now)

    # -- output --------------------------------------------------------------

    def _balance_note(self, session: Session, now: datetime) -> Reply:
        """
        The expiry reminder, stated flatly.

        Use a dated user report and the policy source; never imply a live bank read.
        """
        p = session.profile
        return Reply(
            text=(
                f"{self._reported_balance(p)}\n"
                f"Годовой остаток не переносится после {_fmt_expiry()}. До этой даты {_days_left(now.date())} дней.\n"
                f"Точный остаток — в «Госуслуги Культура».\n"
                f"Правила на {CARD_RULES_2026.as_of}: {CARD_RULES_2026.source}"
            ),
            buttons=["что посмотреть", "другой остаток"],
        )

    @staticmethod
    def _reported_balance(user: UserProfile) -> str:
        if user.balance_general is None:
            return "Остаток пока не указан; доступность по бюджету не подтверждена."
        when = f" ({user.balance_reported_at[:10]})" if user.balance_reported_at else ""
        return f"Последний указанный остаток{when}: {user.balance_general} ₽."

    def _plans(self, session: Session, now: datetime) -> Reply:
        user = session.profile
        buttons = ["что посмотреть", "другой остаток"]
        if user.balance_general is None:
            return Reply("Для расчёта плана нужен точный остаток. Его можно посмотреть в «Госуслуги Культура».", buttons)
        found = candidates(self._events, user, now)
        ranked = self._ranker.score(found, user, session.taste, today=now.date())
        plans = build_plans(ranked, user)
        if not plans:
            return Reply("План из 2–3 событий под эти условия не получился. Можно посмотреть отдельные события или обновить остаток.", buttons)
        titles = {"interests": "По интересам", "variety": "Разные форматы", "budget": "Ближе к остатку"}
        blocks = []
        for plan in plans:
            estimated = any(s.event.price != s.event.max_price for s in plan.items)
            lines = [titles[plan.kind]]
            for s in plan.items:
                price = f"от {s.event.price}" if s.event.price != s.event.max_price else str(s.event.price)
                title = s.event.name if len(s.event.name) <= 100 else s.event.name[:99] + "…"
                venue = s.event.place.name if len(s.event.place.name) <= 80 else s.event.place.name[:79] + "…"
                lines.append(f"• {title} — {price} ₽ · {_fmt_when(s.seance)}\n  {venue}")
                if s.event.sale_link and not (s.event.is_synthetic or self._source.is_synthetic):
                    if len(s.event.sale_link) <= 300:
                        lines.append(f"  {s.event.sale_link}")
                    else:
                        lines.append("  Ссылку на билет уточни у площадки.")
            if estimated:
                lines.append(f"Итого от {plan.total} ₽; расчётный остаток до {plan.remaining} ₽.")
            else:
                lines.append(f"Итого {plan.total} ₽; расчётный остаток {plan.remaining} ₽.")
            blocks.append("\n".join(lines))
        footer = ("Расчёт по ценам каталога: проверь цену и наличие билетов у продавца. "
                  "Билеты покупаются отдельно, деньги с карты не списаны. "
                  "Между событиями заложено 45 минут; время дороги проверь отдельно.")
        if user.balance_cinema is None:
            footer += " Остаток на кино неизвестен, поэтому кино исключено."
        if self._source.is_synthetic or any(s.event.is_synthetic for p in plans for s in p.items):
            footer += " Это тестовые события, покупка недоступна."
        # Keep complete plan blocks within MAX's text limit; don't cut ticket URLs
        # or silently lose budget caveats. Long real catalogue records may yield
        # fewer alternatives than the domain search.
        header = self._reported_balance(user)
        while len(header + "\n\n" + "\n\n".join(blocks) + "\n\n" + footer) > 4000:
            blocks.pop()
        return Reply(header + "\n\n" + "\n\n".join(blocks) + "\n\n" + footer, buttons)

    def _fmt_event(self, scored: Scored, user: UserProfile) -> str:
        event, seance = scored.event, scored.seance
        lines = [
            f"• {event.name}",
            f"  {'от ' if event.price != event.max_price else ''}{event.price} ₽ · {_fmt_when(seance)}",
            f"  {event.place.name}",
        ]
        if user.home is not None:
            km = km_between(user.home, (event.place.lat, event.place.lon))
            lines[2] += f" · {km:.0f} км"
        if event.short_description:
            lines.append(f"  {event.short_description}")
        # Explain the actual score component; do not invent a cultural connection.
        reason = REASON_TEXT.get(scored.top_reason())
        if reason:
            lines.append(f"  Почему: {reason}")
        if event.sale_link and not (event.is_synthetic or self._source.is_synthetic):
            lines.append(f"  Билет: {event.sale_link}")
        return "\n".join(lines)

    def _recommend(
        self, session: Session, now: datetime, preamble: str | None = None
    ) -> Reply:
        user = session.profile
        found = candidates(self._events, user, now)

        if not found:
            return Reply(
                text=(
                    "Под эти условия ничего не нашлось. Можно обновить остаток "
                    "или начать заново и выбрать другое время."
                ),
                buttons=["другой остаток", "заново"],
            )

        ranked = self._ranker.score(found, user, session.taste, today=now.date())
        window = ranked[session.offset : session.offset + 12]
        if not window:
            session.offset = 0
            window = ranked[:12]
        picked = self._ranker.diversify(window, 3)
        session.last_shown = picked

        # Impressions are logged even though nothing reads them yet: a log can be
        # replayed into any future model, and cannot be reconstructed afterwards.
        if self._store is not None:
            self._store.log_many([
                (user.user_id, s.event.id, "impression", "feed", i, session.mood)
                for i, s in enumerate(picked)
            ])

        header = preamble or f"Нашёл {len(found)} вариантов. Вот подходящие:"

        # Admit it when the catalogue has nothing close to what they asked for,
        # instead of quietly serving the nearest thing. A dishonest match costs
        # more trust than an honest miss.
        if session.mood:
            fit = mood_match([s.vector for s in picked], session.mood)
            if fit < 0.15:
                header = (
                    f"Под «{session.mood}» в афише сейчас пусто. "
                    f"Вот что ближе всего по остальному:"
                )

        body = "\n\n".join(self._fmt_event(s, user) for s in picked)
        footer = (
            f"\n{self._reported_balance(user)}"
        )
        if self._source.is_synthetic:
            footer += "\nДанные тестовые, ссылки нерабочие."

        return Reply(
            text=f"{header}\n\n{body}\n{footer}",
            buttons=["собрать план", "ещё", "другое настроение", "сколько осталось"],
        )
