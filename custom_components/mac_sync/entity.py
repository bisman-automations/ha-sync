"""Shared entity plumbing for Mac Sync."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MacSyncStore
from .const import DOMAIN, SIGNAL_UPDATE


def device_info(entry: ConfigEntry, store: MacSyncStore) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=store.data.get("source") or "Mac",
        manufacturer="Apple",
        model="macOS (Mac Sync)",
    )


class MacSyncEntity(Entity):
    """An entity backed by one item (calendar, list, folder, album) from the Mac."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, store: MacSyncStore, section: str, item_id: str) -> None:
        self._store = store
        self._section = section
        self._item_id = item_id
        self._attr_unique_id = f"{entry.entry_id}_{section}_{item_id}"
        self._attr_device_info = device_info(entry, store)
        self._attr_name = (self.item or {}).get("title", item_id)

    @property
    def item(self) -> dict[str, Any] | None:
        return self._store.data[self._section].get(self._item_id)

    @property
    def available(self) -> bool:
        # Deselected on the Mac -> entity goes unavailable (remove it in the UI if you like).
        return self.item is not None

    @callback
    def _handle_update(self) -> None:
        item = self.item
        if item is None:
            return  # setup_dynamic is removing this entity
        self._attr_name = item.get("title", self._attr_name)
        self._refresh()
        self.async_write_ha_state()

    @callback
    def _refresh(self) -> None:
        """Hook for subclasses to recompute cached state."""

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._refresh()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATE, self._handle_update)
        )


def setup_dynamic(
    hass: HomeAssistant,
    entry: ConfigEntry,
    store: MacSyncStore,
    section: str,
    factory: Callable[[str], MacSyncEntity],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Keep one entity per item in a section in step with what the Mac sends.

    New items get an entity. When an item stops being sent (unchecked on the
    Mac, or deleted there), its entity is removed but its entity registry entry
    is kept: Home Assistant then shows it as unavailable and "no longer
    provided", which is what lets you delete it in the UI. If the item comes
    back, the same entity (same unique_id and entity_id) is added again.
    """
    current: dict[str, MacSyncEntity] = {}

    @callback
    def _sync_entities() -> None:
        items = store.data[section]
        for item_id in [i for i in current if i not in items]:
            entity = current.pop(item_id)
            # force_remove=False keeps the registry entry and writes the
            # restored "unavailable" state that makes the entity deletable.
            hass.async_create_task(entity.async_remove(force_remove=False))
        new_ids = [i for i in items if i not in current]
        if new_ids:
            new = {i: factory(i) for i in new_ids}
            current.update(new)
            async_add_entities(list(new.values()))

    _sync_entities()
    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_UPDATE, _sync_entities))
