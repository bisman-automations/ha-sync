"""To-do list entities mirroring macOS Reminders lists (read-only)."""
from __future__ import annotations

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SECTION_REMINDERS
from .entity import MacSyncEntity, setup_dynamic


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    store = hass.data[DOMAIN]
    setup_dynamic(
        hass, entry, store, SECTION_REMINDERS,
        lambda item_id: MacReminderList(entry, store, SECTION_REMINDERS, item_id),
        async_add_entities,
    )


class MacReminderList(MacSyncEntity, TodoListEntity):
    def _refresh(self) -> None:
        items: list[TodoItem] = []
        for raw in (self.item or {}).get("items", []):
            due = None
            if raw.get("due"):
                if raw.get("due_all_day"):
                    due = dt_util.parse_date(raw["due"][:10])
                else:
                    parsed = dt_util.parse_datetime(raw["due"])
                    due = dt_util.as_local(parsed) if parsed else None
            items.append(
                TodoItem(
                    uid=raw.get("uid"),
                    summary=raw.get("title") or "(No title)",
                    status=TodoItemStatus.COMPLETED if raw.get("completed") else TodoItemStatus.NEEDS_ACTION,
                    due=due,
                    description=raw.get("notes"),
                )
            )
        self._attr_todo_items = items
