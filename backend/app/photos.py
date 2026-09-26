"""
Pictures for event cards.

A card without a picture is a wall of text, and a wall of text loses the attention
contest before it starts. MAX accepts an image attachment by URL, fetching it
server-side.

Until the PRO.Культура.РФ key arrives our catalogue is synthetic and carries no real
image URLs, so we map each synthetic event to a **real photograph of the real venue**
taken from the public Культура.РФ listing, matched by a keyword in the venue name.

That means a demo shows a genuine Kazan theatre to a Kazan jury instead of a grey
placeholder. It also means the materials must say plainly what is real here and what
is not: the venues and their photographs are real, the events are not. See
data/venue_photos.json and data/README.md.

When the real feed arrives, events carry their own `image`, and this module becomes
the fallback for the ones that do not.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Event

_DATA = Path(__file__).resolve().parents[2] / "data" / "venue_photos.json"


class PhotoBook:
    """Resolves an event to a picture URL, deterministically."""

    def __init__(self, path: Path | None = None):
        self._prefix = ""
        self._by_keyword: dict[str, list[str]] = {}
        self._source = ""
        try:
            blob = json.loads((path or _DATA).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # No photo file is not an error: every caller must already cope with an
            # event that has no picture.
            return
        self._prefix = blob.get("_prefix", "")
        self._by_keyword = blob.get("by_venue_keyword", {})
        self._source = blob.get("_source", "")

    @property
    def is_available(self) -> bool:
        return bool(self._by_keyword)

    @property
    def source(self) -> str:
        return self._source

    def for_event(self, event: Event) -> str | None:
        """
        A picture for this event, or None.

        Real image first — once the live feed is wired, most events will have one.
        Otherwise a photo of the venue, chosen by the event id so the same event
        always gets the same picture: a card that changes its image between two
        showings looks broken.
        """
        own = getattr(event, "image_url", None)
        if own:
            return own

        venue = event.place.name
        for keyword, urls in self._by_keyword.items():
            if keyword in venue and urls:
                return self._prefix + urls[event.id % len(urls)]
        return None

    def coverage(self, events: list[Event]) -> float:
        if not events:
            return 0.0
        return sum(1 for e in events if self.for_event(e)) / len(events)
