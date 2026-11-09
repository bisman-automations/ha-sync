"""Sensors for Notes folders, Photos albums and sync status."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import MacSyncStore
from .const import DOMAIN, MEDIA_SUBDIR, SECTION_ALBUMS, SECTION_NOTES, SIGNAL_UPDATE
from .entity import MacSyncEntity, device_info, setup_dynamic


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    store: MacSyncStore = hass.data[DOMAIN]
    async_add_entities([LastSyncSensor(entry, store)])
    setup_dynamic(
        hass, entry, store, SECTION_NOTES,
        lambda i: NotesFolderSensor(entry, store, SECTION_NOTES, i), async_add_entities,
    )
    setup_dynamic(
        hass, entry, store, SECTION_ALBUMS,
        lambda i: AlbumSensor(entry, store, SECTION_ALBUMS, i), async_add_entities,
    )


class NotesFolderSensor(MacSyncEntity, SensorEntity):
    """State = number of notes; attribute `notes` holds title/body/modified for each."""

    _attr_icon = "mdi:note-text-outline"
    _attr_native_unit_of_measurement = "notes"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unrecorded_attributes = frozenset({"notes"})

    @property
    def native_value(self) -> int | None:
        item = self.item
        return len(item.get("notes", [])) if item else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        item = self.item or {}
        return {"account": item.get("account"), "notes": item.get("notes", [])}


class AlbumSensor(MacSyncEntity, SensorEntity):
    """State = photos synced to /media/mac_sync/<album>; use media_content_id in cards."""

    _attr_icon = "mdi:image-album"
    _attr_native_unit_of_measurement = "photos"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        item = self.item
        return item.get("synced", 0) if item else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        item = self.item or {}
        slug = item.get("slug", "")
        return {
            "kind": item.get("kind"),
            "album_count": item.get("count"),
            "folder": f"{MEDIA_SUBDIR}/{slug}",
            "media_content_id": f"media-source://media_source/local/{MEDIA_SUBDIR}/{slug}",
        }


class LastSyncSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Last sync"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry, store: MacSyncStore) -> None:
        self._store = store
        self._attr_unique_id = f"{entry.entry_id}_last_sync"
        self._attr_device_info = device_info(entry, store)

    @property
    def native_value(self) -> datetime | None:
        raw = self._store.data.get("last_sync")
        return dt_util.parse_datetime(raw) if raw else None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATE, callback(self.async_write_ha_state))
        )
