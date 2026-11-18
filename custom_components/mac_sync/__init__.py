"""Mac Sync: receive macOS Calendar, Reminders, Notes and Photos pushed from a Mac."""

from __future__ import annotations

from http import HTTPStatus
import logging
from pathlib import Path
import re
import shutil
from typing import Any

from aiohttp import web
import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    EVENT_UPDATED,
    MEDIA_SUBDIR,
    SECTION_ALBUMS,
    SECTIONS,
    SIGNAL_UPDATE,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .schema import clean_payload

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.CALENDAR, Platform.TODO, Platform.SENSOR]
VERSION = "1.1.1"

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_name(value: str) -> str:
    """Make a string safe to use as a single path component."""
    cleaned = _SAFE.sub("-", value).strip(".-")
    return cleaned[:120] or "item"


def media_root(hass: HomeAssistant) -> Path:
    """Folder that holds synced photos (inside the local media source)."""
    base = hass.config.media_dirs.get("local") or hass.config.path("media")
    return Path(base) / MEDIA_SUBDIR


class MacSyncStore:
    """Holds the latest payload from the Mac and persists it across restarts."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, Any] = {s: {} for s in SECTIONS}
        self.data["last_sync"] = None
        self.data["source"] = None

    async def async_load(self) -> None:
        if stored := await self._store.async_load():
            self.data.update(stored)

    async def async_apply(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply a push from the Mac. Returns photo files HA still needs.

        ``payload`` must already have been through
        :func:`.schema.clean_payload`: it is an object, every section sent is a
        list of items that each have a string ``id``, and every album has a
        ``title`` or ``slug``.
        """
        for section in SECTIONS:
            items = payload.get(section)
            if items is None:
                continue  # section not sent: leave as-is
            self.data[section] = {str(item["id"]): item for item in items}
            if section == SECTION_ALBUMS:
                # Settle each album's folder name once, before touching disk.
                for album in self.data[section].values():
                    album["slug"] = safe_name(album.get("slug") or album["title"])
        self.data["last_sync"] = dt_util.utcnow().isoformat()
        self.data["source"] = payload.get("source")

        missing: dict[str, list[str]] = {}
        if payload.get(SECTION_ALBUMS) is not None:
            missing = await self.hass.async_add_executor_job(
                self._reconcile_media, list(self.data[SECTION_ALBUMS].values())
            )
            # Count only what's actually on disk so sensors are honest.
            for album in self.data[SECTION_ALBUMS].values():
                slug = album["slug"]
                album["synced"] = len(album.get("files", [])) - len(
                    missing.get(slug, [])
                )

        self._store.async_delay_save(lambda: self.data, 2)
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)
        self.hass.bus.async_fire(EVENT_UPDATED, {"source": self.data["source"]})
        return {"missing": missing}

    def _reconcile_media(self, albums: list[dict[str, Any]]) -> dict[str, list[str]]:
        """Delete photos no longer in albums and report the ones not on disk yet."""
        root = media_root(self.hass)
        root.mkdir(parents=True, exist_ok=True)
        wanted_dirs: set[str] = set()
        missing: dict[str, list[str]] = {}
        for album in albums:
            slug = album["slug"]  # made safe in async_apply
            wanted_dirs.add(slug)
            folder = root / slug
            folder.mkdir(exist_ok=True)
            wanted = {safe_name(f) for f in album.get("files", [])}
            existing = {p.name for p in folder.iterdir() if p.is_file()}
            for stale in existing - wanted:
                (folder / stale).unlink(missing_ok=True)
            if need := sorted(wanted - existing):
                missing[slug] = need
        for child in root.iterdir():
            if child.is_dir() and child.name not in wanted_dirs:
                shutil.rmtree(child, ignore_errors=True)
        return missing


class PushView(HomeAssistantView):
    """POST /api/mac_sync/push — JSON snapshot from the Mac app."""

    url = "/api/mac_sync/push"
    name = "api:mac_sync:push"

    async def get(self, request: web.Request) -> web.Response:
        hass = request.app[KEY_HASS]
        return self.json({"ok": _store(hass) is not None, "version": VERSION})

    async def post(self, request: web.Request) -> web.Response:
        hass = request.app[KEY_HASS]
        if not request["hass_user"].is_admin:
            return self.json_message("Admin token required", HTTPStatus.UNAUTHORIZED)
        store = _store(hass)
        if store is None:
            return self.json_message(
                "Mac Sync is not set up", HTTPStatus.SERVICE_UNAVAILABLE
            )
        try:
            raw = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON", HTTPStatus.BAD_REQUEST)
        # Reject a body that isn't a push at all (a list, a number, a section
        # that isn't a list, ...) with 400 instead of letting it raise later.
        # Malformed items inside a valid push are skipped and logged by
        # clean_payload, so one bad item can't stop the rest from syncing.
        if not isinstance(raw, dict):
            return self.json_message("Expected a JSON object", HTTPStatus.BAD_REQUEST)
        try:
            cleaned = clean_payload(raw)
        except vol.Invalid as err:
            return self.json_message(
                f"Invalid push: {humanize_error(raw, err)}", HTTPStatus.BAD_REQUEST
            )
        result = await store.async_apply(cleaned.payload)
        response: dict[str, Any] = {"ok": True, **result}
        if cleaned.skipped:
            # The Mac app ignores unknown keys; this is for anyone debugging.
            response["skipped"] = cleaned.skipped
        return self.json(response)


class PhotoView(HomeAssistantView):
    """POST /api/mac_sync/photo — multipart upload of one JPEG (fields: album, filename, file)."""

    url = "/api/mac_sync/photo"
    name = "api:mac_sync:photo"

    async def post(self, request: web.Request) -> web.Response:
        hass = request.app[KEY_HASS]
        if not request["hass_user"].is_admin:
            return self.json_message("Admin token required", HTTPStatus.UNAUTHORIZED)
        if _store(hass) is None:
            return self.json_message(
                "Mac Sync is not set up", HTTPStatus.SERVICE_UNAVAILABLE
            )

        fields: dict[str, Any] = {}
        reader = await request.multipart()
        while (part := await reader.next()) is not None:
            if part.name == "file":
                fields["file"] = await part.read(decode=False)
            elif part.name:
                fields[part.name] = await part.text()

        if not all(k in fields for k in ("album", "filename", "file")):
            return self.json_message(
                "album, filename and file are required", HTTPStatus.BAD_REQUEST
            )

        folder = media_root(hass) / safe_name(fields["album"])
        target = folder / safe_name(fields["filename"])

        def _write() -> None:
            folder.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".part")
            tmp.write_bytes(fields["file"])
            tmp.replace(target)

        await hass.async_add_executor_job(_write)
        return self.json({"ok": True})


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    # Views can't be unregistered, so register them once for the HA lifetime.
    hass.http.register_view(PushView())
    hass.http.register_view(PhotoView())
    return True


def _store(hass: HomeAssistant) -> MacSyncStore | None:
    """The loaded entry's store (there is only one entry), or None."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return getattr(entry, "runtime_data", None)
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    store = MacSyncStore(hass)
    await store.async_load()
    entry.runtime_data = store
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
