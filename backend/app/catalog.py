"""
Where events come from.

One interface, two implementations: the synthetic fixture we have now, and the real
PRO.Культура.РФ API once a key arrives. Nothing above this module knows which is in
use — that is the whole point, and it is why the fixture was generated in the real
API's schema rather than a convenient one of our own.

`is_synthetic` is carried through deliberately so the UI can say so. The brief requires
us to declare simulated data rather than quietly passing it off as real.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .models import Event, Place, Seance


class EventSource(Protocol):
    """Anything that can hand us a catalogue of Pushkin Card events."""

    @property
    def is_synthetic(self) -> bool: ...

    @property
    def as_of(self) -> str: ...

    def all_events(self) -> list[Event]: ...


def _parse_event(raw: dict, synthetic: bool) -> Event | None:
    """
    Turn one API/fixture record into an Event.

    Returns None for records we cannot use — a real feed will contain some. Skipping
    them quietly is right here; a single malformed event must not take down the
    catalogue.
    """
    try:
        places = raw.get("places") or []
        if not places:
            return None
        p = places[0]

        coords = (p.get("mapPosition") or {}).get("coordinates") or []
        if len(coords) != 2:
            return None
        lon, lat = float(coords[0]), float(coords[1])

        seances: list[Seance] = []
        for s in p.get("seances") or []:
            if not s.get("startLocal"):
                continue
            start = datetime.fromisoformat(s["startLocal"])
            end = (
                datetime.fromisoformat(s["endLocal"])
                if s.get("endLocal")
                else start
            )
            seances.append(Seance(start=start, end=end))
        if not seances:
            return None

        addr = p.get("address") or {}
        street = (addr.get("street") or {}).get("name", "")
        house = (addr.get("house") or {}).get("name", "")
        address = ", ".join(x for x in (street, house) if x)

        tags = tuple(t.get("sysName", "") for t in raw.get("tags") or [])
        tag_names = tuple(t.get("name", "") for t in raw.get("tags") or [])

        return Event(
            id=int(raw["_id"]),
            name=raw.get("name", "").strip(),
            age_restriction=int(raw.get("ageRestriction") or 0),
            short_description=(raw.get("shortDescription") or "").strip(),
            category=(raw.get("category") or {}).get("sysName", "prochie"),
            tags=tags,
            tag_names=tag_names,
            price=int(raw.get("price") or 0),
            max_price=int(raw.get("maxPrice") or raw.get("price") or 0),
            sale_link=raw.get("saleLink") or "",
            place=Place(
                name=p.get("name") or raw.get("organizer") or "",
                category=(p.get("category") or {}).get("sysName", "prochee"),
                lat=lat,
                lon=lon,
                address=address,
            ),
            seances=tuple(sorted(seances, key=lambda s: s.start)),
            is_synthetic=synthetic,
        )
    except (KeyError, TypeError, ValueError):
        return None


class FixtureSource:
    """Reads the generated catalogue from disk. See data/README.md."""

    def __init__(self, path: str | Path):
        self._path = Path(path)
        blob = json.loads(self._path.read_text(encoding="utf-8"))
        self._synthetic = bool(blob.get("_synthetic"))
        self._as_of = blob.get("_generated_at", "unknown")
        self._events = [
            e
            for e in (_parse_event(r, self._synthetic) for r in blob.get("events", []))
            if e is not None
        ]

    @property
    def is_synthetic(self) -> bool:
        return self._synthetic

    @property
    def as_of(self) -> str:
        return self._as_of

    def all_events(self) -> list[Event]:
        return list(self._events)


class ProCultureError(RuntimeError):
    """Something went wrong talking to PRO.Культура.РФ."""


class ProCultureSource:
    """
    The real feed: GET https://pro.culture.ru/api/2.5/pushkinsCardEvents

    Ready to use the moment an integration key arrives — see
    docs/outreach/api-key-request.md. Nothing else in the codebase changes, because
    the fixture was generated in this exact schema and `_parse_event` is shared.

    The API caps a page at 100 events, so this pages until it runs dry.
    """

    API_BASE = "https://pro.culture.ru/api/2.5"
    PAGE = 100
    MAX_PAGES = 60  # 6,000 events: far beyond any single region, but not unbounded

    def __init__(
        self,
        api_key: str,
        subordinations: str | None = None,
        locales: str | None = None,
        timeout: float = 30.0,
    ):
        if not api_key:
            raise ValueError("PROCULTURE_API_KEY is empty")
        self._api_key = api_key
        self._subordinations = subordinations
        self._locales = locales
        self._timeout = timeout
        self._as_of = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    @property
    def is_synthetic(self) -> bool:
        return False

    @property
    def as_of(self) -> str:
        return self._as_of

    def _get(self, path: str, **params) -> dict:
        import httpx

        params = {k: v for k, v in params.items() if v is not None}
        params["apiKey"] = self._api_key
        try:
            r = httpx.get(
                f"{self.API_BASE}/{path}",
                params=params,
                timeout=self._timeout,
                headers={"User-Agent": "pushkin-card-assistant/0.1"},
            )
        except Exception as exc:  # network-level
            raise ProCultureError(f"request to /{path} failed: {exc}") from exc

        if r.status_code == 403:
            raise ProCultureError(
                "403 from PRO.Культура.РФ — the apiKey is wrong or the partnership "
                "was ended. See docs/outreach/api-key-request.md"
            )
        if r.status_code != 200:
            raise ProCultureError(f"/{path} returned HTTP {r.status_code}: {r.text[:200]}")
        try:
            return r.json()
        except ValueError as exc:
            raise ProCultureError(f"/{path} returned non-JSON") from exc

    def locales(self, name_query: str | None = None) -> list[dict]:
        """
        Look up locale ids (regions and cities).

        We deliberately do not hardcode Tatarstan's id: it is discovered once with a
        real key and then pinned in configuration, so a wrong guess cannot quietly
        return another region's events.
        """
        body = self._get("locales", nameQuery=name_query, limit=self.PAGE)
        return body.get("locales", [])

    def raw_events(self, **filters) -> list[dict]:
        """Page through the API and return raw records, unparsed."""
        out: list[dict] = []
        for page in range(self.MAX_PAGES):
            body = self._get(
                "pushkinsCardEvents",
                status="accepted",
                subordinations=self._subordinations,
                locales=self._locales,
                limit=self.PAGE,
                offset=page * self.PAGE,
                **filters,
            )
            batch = body.get("events") or []
            out.extend(batch)
            if len(batch) < self.PAGE:
                break
        return out

    def all_events(self) -> list[Event]:
        raw = self.raw_events()
        return [e for e in (_parse_event(r, False) for r in raw) if e is not None]


def build_source(
    api_key: str = "",
    subordinations: str | None = None,
    fixture_path: str | Path = "data/kazan_events.json",
) -> EventSource:
    """
    Pick a source: the real API when a key is configured, the fixture otherwise.

    Falling back rather than crashing is deliberate — a demo that degrades to test
    data with a visible warning beats one that refuses to start. The UI says which
    is in use either way, so nothing is passed off as real that is not.
    """
    if api_key:
        return ProCultureSource(api_key, subordinations=subordinations)
    return FixtureSource(fixture_path)
