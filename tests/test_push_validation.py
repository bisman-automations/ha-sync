"""The push endpoint rejects bodies that aren't a push and skips malformed items.

Raised in the HACS review of Mac Sync (hacs/default#14089): a list body, or an
album without a title, used to raise inside ``async_apply`` and come back as a
500. Now the envelope is checked (400 on failure) and each item and nested
entry is validated on its own (skipped and logged on failure).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aiohttp.test_utils import TestClient
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from custom_components.mac_sync.const import DOMAIN
from custom_components.mac_sync.schema import clean_payload
from homeassistant.core import HomeAssistant

PUSH = "/api/mac_sync/push"

WORK = {"id": "cal-work", "title": "Work", "account": "iCloud", "events": []}
TRIP = {
    "id": "album-trip",
    "title": "Trip",
    "slug": "trip",
    "kind": "My Albums",
    "count": 1,
    "files": ["a_1.jpg"],
}


@pytest.fixture
async def client(hass: HomeAssistant, hass_client, tmp_path: Path) -> TestClient:
    """Set up Mac Sync and return an authenticated (admin) HTTP client."""
    hass.config.media_dirs = {"local": str(tmp_path)}
    entry = MockConfigEntry(domain=DOMAIN, title="Mac Sync", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return await hass_client()


def _store_data(hass: HomeAssistant) -> dict[str, Any]:
    entry = next(iter(hass.config_entries.async_entries(DOMAIN)))
    return entry.runtime_data.data


@pytest.mark.parametrize(
    "body",
    [
        [],
        [{"calendars": []}],
        "calendars",
        42,
        None,
        {"calendars": {"id": "cal-work"}},
        {"albums": "trip"},
        {"source": ["not", "text"]},
    ],
    ids=[
        "empty-list",
        "list-of-objects",
        "string",
        "number",
        "null",
        "section-is-object",
        "section-is-string",
        "source-not-text",
    ],
)
async def test_body_that_is_not_a_push_is_400(
    hass: HomeAssistant, client: TestClient, body: Any
) -> None:
    """Anything but an object with list sections is rejected and changes nothing."""
    before = dict(_store_data(hass))
    resp = await client.post(PUSH, json=body)
    assert resp.status == 400, await resp.text()
    assert "message" in await resp.json()
    assert _store_data(hass) == before


async def test_invalid_json_is_400(client: TestClient) -> None:
    resp = await client.post(
        PUSH, data="{not json", headers={"Content-Type": "application/json"}
    )
    assert resp.status == 400


async def test_album_without_title_is_skipped_not_500(
    hass: HomeAssistant, client: TestClient, tmp_path: Path, caplog
) -> None:
    """The review's example: an album with no title or slug no longer crashes."""
    nameless = {"id": "album-nameless", "files": ["x.jpg"]}
    resp = await client.post(PUSH, json={"source": "Mac", "albums": [nameless, TRIP]})
    assert resp.status == 200, await resp.text()
    body = await resp.json()
    assert body["skipped"] == {"albums": 1}
    assert body["missing"] == {"trip": ["a_1.jpg"]}
    assert list(_store_data(hass)["albums"]) == ["album-trip"]
    assert (tmp_path / "mac_sync" / "trip").is_dir()
    assert "album-nameless" in caplog.text
    assert "needs a title or a slug" in caplog.text


async def test_album_with_slug_but_no_title_is_kept(
    hass: HomeAssistant, client: TestClient
) -> None:
    resp = await client.post(PUSH, json={"albums": [{"id": "a", "slug": "Beach Day"}]})
    assert resp.status == 200
    assert _store_data(hass)["albums"]["a"]["slug"] == "Beach-Day"


@pytest.mark.parametrize(
    "bad_item",
    [
        "cal-work",
        ["cal-work"],
        {"title": "No id"},
        {"id": ""},
        {"id": True},
        {"id": {"nested": 1}},
        {"id": "x", "title": 5},
        {"id": "x", "events": "not a list"},
    ],
)
async def test_malformed_items_are_skipped_and_the_rest_sync(
    hass: HomeAssistant, client: TestClient, bad_item: Any
) -> None:
    resp = await client.post(PUSH, json={"calendars": [bad_item, WORK]})
    assert resp.status == 200, await resp.text()
    assert (await resp.json())["skipped"] == {"calendars": 1}
    assert list(_store_data(hass)["calendars"]) == ["cal-work"]


async def test_integer_ids_are_kept_as_strings(
    hass: HomeAssistant, client: TestClient
) -> None:
    resp = await client.post(PUSH, json={"notes": [{"id": 7, "title": "Seven"}]})
    assert resp.status == 200
    assert "skipped" not in await resp.json()
    assert _store_data(hass)["notes"]["7"]["id"] == "7"


async def test_malformed_nested_entries_are_skipped_not_the_item(
    hass: HomeAssistant, client: TestClient
) -> None:
    """A bad event, reminder or note drops only that entry, not its calendar/list."""
    good_event = {
        "uid": "e1",
        "title": "Lunch",
        "start": "2026-11-17T12:00:00Z",
        "end": "2026-11-17T13:00:00Z",
        "all_day": False,
    }
    payload = {
        "calendars": [{**WORK, "events": [good_event, "nope", {"title": "no start"}]}],
        "reminders": [
            {
                "id": "list",
                "title": "Groceries",
                "items": [{"title": "Milk", "due": 20261117}, {"title": "Eggs"}],
            }
        ],
        "notes": [
            {"id": "folder", "title": "Recipes", "notes": [None, {"title": "Pie"}]}
        ],
    }
    resp = await client.post(PUSH, json=payload)
    assert resp.status == 200, await resp.text()
    assert (await resp.json())["skipped"] == {
        "calendars": 2,
        "reminders": 1,
        "notes": 1,
    }
    await hass.async_block_till_done()
    data = _store_data(hass)
    assert data["calendars"]["cal-work"]["events"] == [good_event]
    assert data["reminders"]["list"]["items"] == [{"title": "Eggs"}]
    assert data["notes"]["folder"]["notes"] == [{"title": "Pie"}]


async def test_omitted_and_null_sections_are_left_alone(
    hass: HomeAssistant, client: TestClient
) -> None:
    assert (await client.post(PUSH, json={"calendars": [WORK]})).status == 200
    assert (await client.post(PUSH, json={"calendars": None})).status == 200
    assert (await client.post(PUSH, json={"source": "Mac"})).status == 200
    assert list(_store_data(hass)["calendars"]) == ["cal-work"]


async def test_unknown_keys_are_kept_for_newer_mac_apps(
    hass: HomeAssistant, client: TestClient
) -> None:
    resp = await client.post(
        PUSH, json={"future": 1, "calendars": [{**WORK, "emoji": "📅"}]}
    )
    assert resp.status == 200
    assert _store_data(hass)["calendars"]["cal-work"]["emoji"] == "📅"


def test_clean_payload_raises_on_a_bad_envelope() -> None:
    with pytest.raises(vol.Invalid):
        clean_payload({"reminders": 3})
    with pytest.raises(vol.Invalid):
        clean_payload([1, 2])


def test_clean_payload_full_mac_app_payload_passes_untouched() -> None:
    """Everything the Mac app sends (Models.swift) validates with nothing skipped."""
    payload = {
        "source": "Studio",
        "calendars": [
            {
                "id": "c",
                "title": "Home",
                "account": "iCloud",
                "color": "#FF0000",
                "events": [
                    {
                        "uid": "u",
                        "title": "T",
                        "start": "2026-11-17",
                        "end": "2026-11-18",
                        "all_day": True,
                    }
                ],
            }
        ],
        "reminders": [
            {
                "id": "r",
                "title": "L",
                "account": "iCloud",
                "items": [
                    {
                        "uid": "i",
                        "title": "Milk",
                        "completed": False,
                        "due": "2026-11-18",
                        "due_all_day": True,
                    }
                ],
            }
        ],
        "notes": [
            {
                "id": "n",
                "title": "F",
                "account": "iCloud",
                "notes": [
                    {
                        "id": "x",
                        "title": "Pie",
                        "body": "…",
                        "modified": "2026-11-17T10:00:00Z",
                    }
                ],
            }
        ],
        "albums": [TRIP],
    }
    result = clean_payload(payload)
    assert result.skipped == {}
    assert result.payload == payload
