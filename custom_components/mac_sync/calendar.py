"""Calendar entities mirroring macOS Calendar calendars."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import SECTION_CALENDARS
from .entity import MacSyncEntity, setup_dynamic

# Coordinator or push updates; nothing polls on its own.
PARALLEL_UPDATES = 0


def _to_event(raw: dict[str, Any]) -> CalendarEvent | None:
    try:
        if raw.get("all_day"):
            start: date | datetime = date.fromisoformat(raw["start"][:10])
            end: date | datetime = date.fromisoformat(raw["end"][:10])
            if end <= start:
                end = start + timedelta(days=1)
        else:
            start = dt_util.parse_datetime(raw["start"])
            end = dt_util.parse_datetime(raw["end"])
            if start is None or end is None:
                return None
            start, end = dt_util.as_local(start), dt_util.as_local(end)
            if end <= start:
                end = start + timedelta(minutes=1)
    except (KeyError, ValueError, TypeError):
        return None
    return CalendarEvent(
        start=start,
        end=end,
        summary=raw.get("title") or "(No title)",
        description=raw.get("notes"),
        location=raw.get("location"),
        uid=raw.get("uid"),
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    store = entry.runtime_data
    setup_dynamic(
        hass,
        entry,
        store,
        SECTION_CALENDARS,
        lambda item_id: MacCalendar(entry, store, SECTION_CALENDARS, item_id),
        async_add_entities,
    )


class MacCalendar(MacSyncEntity, CalendarEntity):
    _events: list[CalendarEvent] = []

    def _refresh(self) -> None:
        raw = (self.item or {}).get("events", [])
        events = [e for e in (_to_event(r) for r in raw) if e is not None]
        self._events = sorted(events, key=lambda e: e.start_datetime_local)

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        return next((e for e in self._events if e.end_datetime_local > now), None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        item = self.item or {}
        return {"color": item.get("color"), "account": item.get("account")}

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return [
            e
            for e in self._events
            if e.end_datetime_local > start_date and e.start_datetime_local < end_date
        ]
