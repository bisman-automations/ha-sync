"""Unchecking an item on the Mac makes its entity deletable in Home Assistant."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mac_sync.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

WORK = {
    "id": "cal-work",
    "title": "Work",
    "account": "iCloud",
    "color": "#FF0000",
    "events": [],
}
HOME = {
    "id": "cal-home",
    "title": "Home",
    "account": "iCloud",
    "color": "#00FF00",
    "events": [],
}
GROCERIES = {
    "id": "list-groceries",
    "title": "Groceries",
    "account": "iCloud",
    "items": [],
}
RECIPES = {"id": "folder-recipes", "title": "Recipes", "account": "iCloud", "notes": []}
TRIP = {
    "id": "album-trip",
    "title": "Trip",
    "slug": "trip",
    "kind": "My Albums",
    "count": 1,
    "files": ["a_1.jpg"],
}


@pytest.fixture
async def push(hass: HomeAssistant, hass_client, tmp_path: Path):
    """Set up the integration and return a function that POSTs a payload like the Mac app."""
    hass.config.media_dirs = {"local": str(tmp_path)}
    entry = MockConfigEntry(domain=DOMAIN, title="Mac Sync", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    client = await hass_client()

    async def _push(**sections: Any) -> dict[str, Any]:
        resp = await client.post(
            "/api/mac_sync/push", json={"source": "Test Mac", **sections}
        )
        assert resp.status == 200, await resp.text()
        await hass.async_block_till_done()
        return await resp.json()

    return _push


def _entity_id(hass: HomeAssistant, platform: str, section: str, item_id: str) -> str:
    registry = er.async_get(hass)
    entry = next(iter(hass.config_entries.async_entries(DOMAIN)))
    entity_id = registry.async_get_entity_id(
        platform, DOMAIN, f"{entry.entry_id}_{section}_{item_id}"
    )
    assert entity_id, f"no {platform} entity for {item_id}"
    return entity_id


def _assert_deletable(hass: HomeAssistant, entity_id: str) -> None:
    """Unavailable and 'restored': the state HA's UI requires before it offers Delete."""
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get("restored") is True
    assert er.async_get(hass).async_get(entity_id) is not None  # registry entry kept


async def test_unchecked_calendar_becomes_deletable(hass: HomeAssistant, push) -> None:
    await push(calendars=[WORK, HOME])
    work = _entity_id(hass, "calendar", "calendars", "cal-work")
    home = _entity_id(hass, "calendar", "calendars", "cal-home")
    assert hass.states.get(work).state != STATE_UNAVAILABLE

    await push(calendars=[HOME])  # "Work" unchecked on the Mac

    _assert_deletable(hass, work)
    assert hass.states.get(home).state != STATE_UNAVAILABLE

    # Deleting it in the UI removes it from the registry and the state machine.
    er.async_get(hass).async_remove(work)
    await hass.async_block_till_done()
    assert hass.states.get(work) is None


async def test_rechecked_calendar_comes_back_with_same_entity_id(
    hass: HomeAssistant, push
) -> None:
    await push(calendars=[WORK])
    work = _entity_id(hass, "calendar", "calendars", "cal-work")
    await push(calendars=[])  # every calendar unchecked
    _assert_deletable(hass, work)

    await push(calendars=[WORK])  # checked again

    state = hass.states.get(work)
    assert state.state != STATE_UNAVAILABLE
    assert "restored" not in state.attributes
    assert _entity_id(hass, "calendar", "calendars", "cal-work") == work


async def test_omitted_section_is_left_alone(hass: HomeAssistant, push) -> None:
    """A section the Mac couldn't read (e.g. permission revoked) isn't sent and must not go unavailable."""
    await push(calendars=[WORK])
    work = _entity_id(hass, "calendar", "calendars", "cal-work")
    await push(reminders=[GROCERIES])  # no "calendars" key at all
    assert hass.states.get(work).state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("platform", "section", "item"),
    [
        ("todo", "reminders", GROCERIES),
        ("sensor", "notes", RECIPES),
        ("sensor", "albums", TRIP),
    ],
)
async def test_other_unchecked_items_become_deletable(
    hass: HomeAssistant,
    push,
    tmp_path: Path,
    platform: str,
    section: str,
    item: dict[str, Any],
) -> None:
    await push(**{section: [item]})
    entity_id = _entity_id(hass, platform, section, item["id"])
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    await push(**{section: []})

    _assert_deletable(hass, entity_id)
    if section == "albums":
        assert not (
            tmp_path / "mac_sync" / "trip"
        ).exists()  # its photo folder is removed too


async def test_entities_for_unchecked_items_stay_gone_after_restart(
    hass: HomeAssistant, push
) -> None:
    await push(calendars=[WORK, HOME])
    work = _entity_id(hass, "calendar", "calendars", "cal-work")
    await push(calendars=[HOME])

    entry = next(iter(hass.config_entries.async_entries(DOMAIN)))
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    _assert_deletable(hass, work)
