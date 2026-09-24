"""
The conversation.

Transport-agnostic on purpose: this module takes text in and returns text plus
buttons out, and knows nothing about MAX. That means we can run the whole thing in
a terminal today, without a bot token, and plug MAX in later without touching any
of the logic here.

Register rules from docs/design/tone.md apply to every string in this file:
no slang, no exclamation-mark enthusiasm, no urgency theatre. State the fact, give
the options, let them decide. And rule 3 — say plainly why we are recommending
something, because a declared persuasion cannot be caught out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum, auto

from .catalog import EventSource
from .db import Store
from .config import BALANCE_EXPIRES, CARD_RULES_2026, ELIGIBLE_AGE_MAX, ELIGIBLE_AGE_MIN
from .filters import candidates, km_between
from .labeling import label_all
from .models import Event, Seance, UserProfile
from .taste import MOOD_TARGETS, Ranker, Scored, Taste, mood_match, quiz_cards

WEEKDAYS_RU = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")
MONTHS_RU = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)

QUIZ_LENGTH = 5

# Why an event was picked, in plain words. Keyed by the strongest score component.
REASON_TEXT = {
    "taste": "похоже на то, что ты отметил(а)",
    "discovery": "необычный формат, такого мало в афише",
    "budget": "хорошо ложится в остаток",
    "convenience": "рядом и в удобное время",
    "urgency": "успеваешь до конца года",
}


class Step(Enum):
    NEW = auto()
    ASK_AGE = auto()
    ASK_BALANCE = auto()
    ASK_TIME = auto()
    ASK_MOOD = auto()
    QUIZ = auto()
    READY = auto()


@dataclass
class Reply:
    """What the bot says back. `buttons` are suggested answers, not a keyboard spec."""

    text: str
    buttons: list[str] = field(default_factory=list)


@dataclass
class Session:
    profile: UserProfile
    taste: Taste = field(default_factory=Taste)
    step: Step = Step.NEW
    offset: int = 0
    quiz: list[Event] = field(default_factory=list)
    quiz_at: int = 0
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
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None


class Dialog:
    """
    One bot, many sessions.

    Sessions are in memory. Fine for an MVP and a demo; when they need to survive a
    restart, this is the one place to change.
    """

    def __init__(self, source: EventSource, store: Store | None = None):
        self._source = source
        self._store = store
        self._events = source.all_events()
        self._by_id = {e.id: e for e in self._events}
        self._labels = label_all(self._events)
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
            saved = self._store.load_session(user_id)
            if saved:
                try:
                    session.step = Step[saved["step"]]
                except KeyError:
                    session.step = Step.NEW
                session.offset = saved["list_offset"]
                session.mood = saved["mood"]
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
        )

    def reset(self, user_id: str) -> None:
        self._sessions.pop(user_id, None)

    # -- routing -------------------------------------------------------------

    def handle(self, user_id: str, text: str, now: datetime | None = None) -> Reply:
        now = now or datetime.now()
        text = (text or "").strip()
        session = self._session(user_id)

        if text.lower() in ("/start", "начать", "заново", "/reset"):
            self.reset(user_id)
            return self._greet(self._session(user_id))

        handlers = {
            Step.NEW: lambda: self._greet(session),
            Step.ASK_AGE: lambda: self._take_age(session, text),
            Step.ASK_BALANCE: lambda: self._take_balance(session, text),
            Step.ASK_TIME: lambda: self._take_time(session, text),
            Step.ASK_MOOD: lambda: self._take_mood(session, text, now),
            Step.QUIZ: lambda: self._take_quiz(session, text, now),
            Step.READY: lambda: self._take_command(session, text, now),
        }
        reply = handlers[session.step]()
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
                f"Сколько осталось на карте?\n"
                f"Номинал на год — {r.total} ₽, из них {r.cinema_cap} ₽ на кино.\n"
                f"Данные на {r.as_of}, источник: {r.source}"
            ),
            buttons=["5000", "3200", "1500", "не знаю"],
        )

    def _take_balance(self, session: Session, text: str) -> Reply:
        r = CARD_RULES_2026
        note = ""
        if text.lower() in ("не знаю", "хз", "?"):
            session.profile.balance_general = r.total
            session.profile.balance_cinema = r.cinema_cap
            note = (
                f"Считаю, что карта полная — {r.total} ₽. "
                f"Точный остаток в «Госуслуги Культура», напиши число, если другое.\n\n"
            )
        else:
            amount = _parse_int(text)
            if amount is None or amount < 0 or amount > r.total:
                return Reply(
                    text=f"Введи число от 0 до {r.total}.",
                    buttons=["5000", "3200", "1500", "не знаю"],
                )
            session.profile.balance_general = amount
            session.profile.balance_cinema = min(amount, r.cinema_cap)

        session.step = Step.ASK_TIME
        return Reply(
            text=note + "Когда тебе удобно ходить?",
            buttons=["вечером и в выходные", "только в выходные", "только вечером"],
        )

    def _take_time(self, session: Session, text: str) -> Reply:
        t = text.lower()
        only = "только" in t
        session.profile.free_weekends = not (only and "вечер" in t)
        session.profile.free_evenings = not (only and "выходн" in t)

        session.step = Step.ASK_MOOD
        return Reply(
            text="Чего сейчас хочется?",
            buttons=list(MOOD_TARGETS.keys()),
        )

    def _take_mood(self, session: Session, text: str, now: datetime) -> Reply:
        # Mood, not momentary emotion: it is stable over a session and, per the
        # affective-recommender literature, it is what helps in cold start.
        matched = next((m for m in MOOD_TARGETS if m.lower() == text.lower()), None)
        if matched:
            session.mood = matched
            session.taste.add_mood(matched)

        session.quiz = quiz_cards(self._events, self._ranker, n=QUIZ_LENGTH, now=now)
        session.quiz_at = 0
        if not session.quiz:
            session.step = Step.READY
            return self._recommend(session, now)

        session.step = Step.QUIZ
        return Reply(
            text=(
                "Теперь несколько карточек — скажи, что из этого интересно.\n"
                f"Это {QUIZ_LENGTH} вопросов, чтобы не показывать тебе случайное.\n\n"
                + self._quiz_card(session)
            ),
            buttons=["интересно", "не моё", "пропустить"],
        )

    def _log(
        self, session: Session, event_id: int, signal: str,
        surface: str | None = None, position: int | None = None,
    ) -> None:
        if self._store is None:
            return
        self._store.log(
            session.profile.user_id, event_id, signal,
            surface=surface, position=position, mood=session.mood,
        )

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
        if t in ("ещё", "еще", "дальше", "/more"):
            session.offset += 3
            return self._recommend(session, now)
        if t in ("сколько осталось", "баланс", "/balance"):
            return self._balance_note(session)
        if t in ("другой остаток", "/balance_set"):
            session.step = Step.ASK_BALANCE
            return Reply(text="Сколько сейчас на карте?", buttons=["5000", "3200", "1500"])
        if t in ("другое настроение", "/mood"):
            session.mood = None
            session.step = Step.ASK_MOOD
            return Reply(text="Чего сейчас хочется?", buttons=list(MOOD_TARGETS.keys()))

        # Treat anything else as "show me again", but learn from it: naming an event
        # we showed is a signal about it.
        for i, scored in enumerate(session.last_shown):
            if t and t in scored.event.name.lower():
                session.taste.add(scored.vector, "buy_click")
                self._log(session, scored.event.id, "buy_click", surface="feed", position=i)
                break
        session.offset = 0
        return self._recommend(session, now)

    # -- output --------------------------------------------------------------

    def _balance_note(self, session: Session) -> Reply:
        """
        The expiry reminder, stated flatly.

        tone.md rule 5: no "не упусти", no countdown theatre. Reactance research says
        pressure produces resistance, and the fact is urgent enough by itself.
        """
        p = session.profile
        return Reply(
            text=(
                f"По твоим словам на карте {p.balance_general} ₽. "
                f"Сгорают {_fmt_expiry()} — это {_days_left()} дней.\n"
                f"Точный остаток — в «Госуслуги Культура»."
            ),
            buttons=["что посмотреть", "другой остаток"],
        )

    def _fmt_event(self, scored: Scored, user: UserProfile) -> str:
        event, seance = scored.event, scored.seance
        lines = [
            f"• {event.name}",
            f"  {event.price} ₽ · {_fmt_when(seance)}",
            f"  {event.place.name}",
        ]
        if user.home is not None:
            km = km_between(user.home, (event.place.lat, event.place.lon))
            lines[2] += f" · {km:.0f} км"
        if event.short_description:
            lines.append(f"  {event.short_description}")
        # Rule 3: say why. A detected hidden persuasion is manipulation; a declared
        # one is an explanation.
        reason = REASON_TEXT.get(scored.top_reason())
        if reason:
            lines.append(f"  Почему: {reason}")
        if event.sale_link:
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
                    "Под эти условия ничего не нашлось. "
                    "Можно поискать шире — например, если готов(а) ездить дальше "
                    "или ходить и днём."
                ),
                buttons=["заново"],
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
            f"\nОстаток {user.balance_general} ₽, сгорает через {_days_left()} дней."
        )
        if self._source.is_synthetic:
            footer += "\nДанные тестовые, ссылки нерабочие."

        return Reply(
            text=f"{header}\n\n{body}\n{footer}",
            buttons=["ещё", "другое настроение", "сколько осталось"],
        )
