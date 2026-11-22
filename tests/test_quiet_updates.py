"""Entities write only when what they show changed; photo uploads update album counts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import aiohttp
from aiohttp.test_utils import TestClient
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mac_sync.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

WORK = {"id": "cal-work", "title": "Work", "account": "iCloud", "events": []}
GROCERIES = {"id": "list-groceries", "title": "Groceries", "items": []}
TRIP = {
    "id": "album-trip",
    "title": "Trip",
    "slug": "trip",
    "kind": "My Albums",
    "count": 2,
    "files": ["a_1.jpg", "b_2.jpg"],
}


@pytest.fixture
async def client(hass: HomeAssistant, hass_client, tmp_path: Path) -> TestClient:
    hass.config.media_dirs = {"local": str(tmp_path)}
    entry = MockConfigEntry(domain=DOMAIN, title="Mac Sync", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return await hass_client()


async def _push(hass: HomeAssistant, client: TestClient, **sections: Any) -> None:
    resp = await client.post(
        "/api/mac_sync/push", json={"source": "Test Mac", **sections}
    )
    assert resp.status == 200, await resp.text()
    await hass.async_block_till_done()


async def _upload(
    hass: HomeAssistant, client: TestClient, album: str, filename: str
) -> None:
    form = aiohttp.FormData()
    form.add_field("album", album)
    form.add_field("filename", filename)
    form.add_field("file", b"\xff\xd8jpeg", filename=filename)
    resp = await client.post("/api/mac_sync/photo", data=form)
    assert resp.status == 200, await resp.text()
    await hass.async_block_till_done()


def _entity_id(hass: HomeAssistant, platform: str, unique_suffix: str) -> str:
    entry = next(iter(hass.config_entries.async_entries(DOMAIN)))
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{entry.entry_id}_{unique_suffix}"
    )
    assert entity_id
    return entity_id


def _reported(hass: HomeAssistant, entity_id: str):
    return hass.states.get(entity_id).last_reported


async def test_unchanged_items_are_not_written_again(
    hass: HomeAssistant, client: TestClient
) -> None:
    await _push(hass, client, calendars=[WORK], reminders=[GROCERIES])
    work = _entity_id(hass, "calendar", "calendars_cal-work")
    before = _reported(hass, work)

    # Another section changes, then the calendar is sent again unchanged.
    await _push(hass, client, reminders=[{**GROCERIES, "title": "Shopping"}])
    await _push(hass, client, calendars=[dict(WORK)])
    assert _reported(hass, work) == before

    # A real change is still written.
    await _push(hass, client, calendars=[{**WORK, "title": "Office"}])
    assert _reported(hass, work) != before
    assert hass.states.get(work).attributes["friendly_name"].endswith("Office")


async def test_photo_upload_updates_album_count_at_once(
    hass: HomeAssistant, client: TestClient, tmp_path: Path
) -> None:
    await _push(hass, client, albums=[TRIP])
    album = _entity_id(hass, "sensor", "albums_album-trip")
    last_sync = _entity_id(hass, "sensor", "last_sync")
    assert hass.states.get(album).state == "0"
    sync_reported = _reported(hass, last_sync)

    await _upload(hass, client, "trip", "a_1.jpg")
    assert (tmp_path / "mac_sync" / "trip" / "a_1.jpg").is_file()
    assert hass.states.get(album).state == "1"
    # The sync time didn't change, so that sensor isn't written.
    assert _reported(hass, last_sync) == sync_reported

    # Replacing a photo, or one the album doesn't list, doesn't count.
    await _upload(hass, client, "trip", "a_1.jpg")
    await _upload(hass, client, "trip", "other.jpg")
    assert hass.states.get(album).state == "1"

    await _upload(hass, client, "trip", "b_2.jpg")
    assert hass.states.get(album).state == "2"

    # The next push agrees with the count kept in between.
    await _push(hass, client, albums=[TRIP])
    assert hass.states.get(album).state == "2"
