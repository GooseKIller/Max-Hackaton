"""Public, stateless planner: never reads a MAX identity or a saved profile.

All money/age inputs are supplied explicitly for this calculation. This is not the
authenticated bot-profile API. Limit body size at the edge before public deployment.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import BALANCE_EXPIRES, CARD_RULES_2026, ELIGIBLE_AGE_MIN, ELIGIBLE_AGE_MAX
from .filters import candidates
from .labeling import label_all
from .models import UserProfile
from .plans import build_plans
from .taste import Ranker, Scored, Taste

router = APIRouter(prefix="/api/planner", tags=["Stateless budget planner"])

CATEGORIES = {
    "spektakli": "Театр", "vystavki": "Выставки", "koncerty": "Концерты",
    "ekskursii": "Экскурсии", "kino": "Кино", "prochie": "Другое",
}
Category = Literal["spektakli", "vystavki", "koncerty", "ekskursii", "kino", "prochie"]
DISPLAY_CATEGORIES = {**CATEGORIES, "obuchenie": "Обучение", "vstrechi": "Встречи", "prazdniki": "Праздники"}


def local_now() -> datetime:
    return datetime.now(ZoneInfo("Europe/Moscow")).replace(tzinfo=None)


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    age: int = Field(strict=True, ge=ELIGIBLE_AGE_MIN, le=ELIGIBLE_AGE_MAX)
    balance: int = Field(strict=True, ge=0, le=CARD_RULES_2026.total)
    cinema_balance: int | None = Field(default=None, strict=True, ge=0, le=CARD_RULES_2026.cinema_cap)
    categories: list[Category] = Field(default_factory=list, max_length=len(CATEGORIES))
    availability: Literal["both", "evenings", "weekends"] = "both"

    @model_validator(mode="after")
    def coherent_budget(self):
        if self.cinema_balance is not None and self.cinema_balance > self.balance:
            raise ValueError("Остаток на кино не может быть больше общего остатка.")
        if len(set(self.categories)) != len(self.categories):
            raise ValueError("Категории не должны повторяться.")
        return self


class EventView(BaseModel):
    id: int
    title: str
    category: str
    category_label: str
    description: str
    venue: str
    address: str
    age: int
    start: str
    end: str
    price: int
    price_is_minimum: bool
    ticket_url: str | None


class PlanView(BaseModel):
    kind: Literal["interests", "variety", "budget"]
    title: str
    explanation: str
    events: list[EventView]
    total: int
    cinema_total: int
    remaining: int
    estimated: bool


class PlannerResult(BaseModel):
    status: Literal["ready", "no_plans", "no_events", "horizon_ended"]
    plans: list[PlanView]
    events: list[EventView]
    balance: int
    cinema_balance: int | None
    calculated_at: str
    synthetic: bool
    catalogue_as_of: str
    horizon_end: str
    transfer_minutes: int = 45


def ticket_url(url: str, synthetic: bool) -> str | None:
    """Catalogue data is untrusted. Return HTTPS seller links, never script URLs."""
    if synthetic or len(url) > 2048 or any(ord(c) < 33 for c in url):
        return None
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if (parsed.scheme != "https" or not host or parsed.username or parsed.password
                or host.endswith(".invalid") or host in ("localhost", "127.0.0.1", "::1")):
            return None
        return url
    except ValueError:
        return None


def event_view(s: Scored, synthetic: bool) -> EventView:
    e = s.event
    return EventView(
        id=e.id, title=e.name, category=e.category,
        category_label=DISPLAY_CATEGORIES.get(e.category, "Другое"),
        description=e.short_description, venue=e.place.name, address=e.place.address,
        age=e.age_restriction, start=s.seance.start.isoformat(), end=s.seance.end.isoformat(),
        price=e.price, price_is_minimum=e.max_price != e.price,
        ticket_url=ticket_url(e.sale_link, synthetic or e.is_synthetic),
    )


class PlannerService:
    def __init__(self, source):
        self.source = source
        self.events = source.all_events()
        self.ranker = Ranker(self.events, label_all(self.events))

    def calculate(self, body: PlanRequest, now: datetime) -> PlannerResult:
        user = UserProfile("stateless", age=body.age, balance_general=body.balance,
                           balance_cinema=body.cinema_balance,
                           free_evenings=body.availability != "weekends",
                           free_weekends=body.availability != "evenings")
        found = candidates(self.events, user, now)
        if body.categories:
            found = [(e, s) for e, s in found
                     if (e.category if e.category in CATEGORIES else "prochie") in body.categories]
        # Same planning horizon for the event alternatives and the multi-event plan.
        found = [(e, s) for e, s in found if s.end > s.start and s.end.date().isoformat() <= BALANCE_EXPIRES]
        taste = Taste(weights={f"cat:{c}": 1.0 for c in body.categories})
        ranked = self.ranker.score(found, user, taste, today=now.date())
        plans = build_plans(ranked, user)
        synthetic = self.source.is_synthetic or any(e.is_synthetic for e in self.events)
        titles = {"interests": "Под твои условия", "variety": "Разные форматы", "budget": "Ближе к остатку"}
        reasons = {
            "interests": "Выше в подборе по выбранным условиям. Это рекомендация, а не гарантия, что понравится.",
            "variety": "В этом плане есть события из разных категорий.",
            "budget": "Меньше остаток среди ещё не показанных сочетаний из первых 30 кандидатов.",
        }
        views = [PlanView(kind=p.kind, title=titles[p.kind], explanation=reasons[p.kind],
                          events=[event_view(s, synthetic) for s in p.items], total=p.total,
                          cinema_total=p.cinema_total, remaining=p.remaining,
                          estimated=any(s.event.max_price != s.event.price for s in p.items))
                 for p in plans]
        status = ("horizon_ended" if now.date().isoformat() > BALANCE_EXPIRES else
                  "ready" if plans else "no_plans" if ranked else "no_events")
        return PlannerResult(status=status, plans=views,
                             events=[event_view(s, synthetic) for s in self.ranker.diversify(ranked, 6)],
                             balance=body.balance, cinema_balance=body.cinema_balance,
                             calculated_at=now.isoformat(), synthetic=synthetic,
                             catalogue_as_of=self.source.as_of, horizon_end=BALANCE_EXPIRES)


@router.get("/meta")
def metadata(request: Request, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    source = request.app.state.planner.source
    return {
        "city": "Казань", "synthetic": source.is_synthetic,
        "catalogue_as_of": source.as_of, "horizon_end": BALANCE_EXPIRES,
        "total_limit": CARD_RULES_2026.total, "cinema_limit": CARD_RULES_2026.cinema_cap,
        "age_min": ELIGIBLE_AGE_MIN, "age_max": ELIGIBLE_AGE_MAX,
        "rules_as_of": CARD_RULES_2026.as_of, "rules_source": CARD_RULES_2026.source,
        "categories": [{"id": k, "label": v} for k, v in CATEGORIES.items()],
    }


@router.post("/plans", response_model=PlannerResult)
def calculate(body: PlanRequest, request: Request, response: Response) -> PlannerResult:
    response.headers["Cache-Control"] = "no-store"
    return request.app.state.planner.calculate(body, local_now())
