"""Validation for the JSON the Mac app pushes to ``/api/mac_sync/push``.

The push endpoint takes a snapshot from the Mac app (see
``mac/Sources/HASync/Models.swift``). Anything can be POSTed to it, though, so
the body is checked in two layers before it reaches the store:

1. **The envelope** (:data:`PAYLOAD_SCHEMA`). The body has to be a JSON object,
   ``source`` has to be text, and every section that is sent has to be a list.
   Anything else is a client error: the view answers ``400 Bad Request`` and
   nothing is changed.
2. **Each item and each nested entry** (:func:`clean_payload`). A calendar,
   list, folder or album that is missing what Mac Sync needs (an ``id``; an
   album also needs a ``title`` or ``slug``) is skipped and logged instead of
   failing the whole push, so one odd item can't stop everything else from
   syncing. The same goes for a single event, reminder or note inside an item.

Unknown keys are kept everywhere (``vol.ALLOW_EXTRA``) so a newer Mac app can
send extra fields without an older Home Assistant rejecting the push.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import logging
from typing import Any

import voluptuous as vol
from voluptuous.humanize import humanize_error

from .const import (
    SECTION_ALBUMS,
    SECTION_CALENDARS,
    SECTION_NOTES,
    SECTION_REMINDERS,
    SECTIONS,
)

_LOGGER = logging.getLogger(__name__)

# Optional text the Mac app may leave out or send as null (Swift encodes a nil
# optional by omitting the key, but other clients may send null).
_OPTIONAL_TEXT = vol.Any(None, str)


def _item_id(value: Any) -> str:
    """Accept a non-empty string or integer id and return it as a string.

    ``bool`` is rejected even though it is an ``int`` subclass: ``true`` is
    never a meaningful id.
    """
    if isinstance(value, bool) or not isinstance(value, str | int):
        raise vol.Invalid("expected a string or integer id")
    text = str(value)
    if not text:
        raise vol.Invalid("id must not be empty")
    return text


# --- Envelope -----------------------------------------------------------------

#: The top level of a push. A section that is omitted or null is left as it is
#: (the Mac couldn't read it, e.g. permission was revoked); a list replaces it.
PAYLOAD_SCHEMA = vol.Schema(
    {
        vol.Optional("source"): _OPTIONAL_TEXT,
        **{vol.Optional(section): vol.Any(None, list) for section in SECTIONS},
    },
    extra=vol.ALLOW_EXTRA,
)


# --- Nested entries (inside an item) ------------------------------------------

EVENT_SCHEMA = vol.Schema(
    {
        vol.Required("start"): str,
        vol.Required("end"): str,
        vol.Optional("uid"): _OPTIONAL_TEXT,
        vol.Optional("title"): _OPTIONAL_TEXT,
        vol.Optional("all_day"): bool,
        vol.Optional("location"): _OPTIONAL_TEXT,
        vol.Optional("notes"): _OPTIONAL_TEXT,
    },
    extra=vol.ALLOW_EXTRA,
)

REMINDER_SCHEMA = vol.Schema(
    {
        vol.Optional("uid"): _OPTIONAL_TEXT,
        vol.Optional("title"): _OPTIONAL_TEXT,
        vol.Optional("completed"): bool,
        vol.Optional("due"): _OPTIONAL_TEXT,
        vol.Optional("due_all_day"): bool,
        vol.Optional("notes"): _OPTIONAL_TEXT,
    },
    extra=vol.ALLOW_EXTRA,
)

NOTE_SCHEMA = vol.Schema(
    {
        vol.Optional("id"): _OPTIONAL_TEXT,
        vol.Optional("title"): _OPTIONAL_TEXT,
        vol.Optional("body"): _OPTIONAL_TEXT,
        vol.Optional("modified"): _OPTIONAL_TEXT,
    },
    extra=vol.ALLOW_EXTRA,
)


# --- Items (one entity each) --------------------------------------------------

_ITEM_BASE = {
    vol.Required("id"): _item_id,
    vol.Optional("title"): str,
    vol.Optional("account"): _OPTIONAL_TEXT,
}


def _album_has_name(album: dict[str, Any]) -> dict[str, Any]:
    """An album's photo folder is named from its slug, or its title if no slug."""
    if not (album.get("slug") or album.get("title")):
        raise vol.Invalid("an album needs a title or a slug")
    return album


ITEM_SCHEMAS: dict[str, vol.Schema] = {
    # A calendar may arrive without events: an empty calendar is still one.
    SECTION_CALENDARS: vol.Schema(
        {
            **_ITEM_BASE,
            vol.Optional("color"): _OPTIONAL_TEXT,
            vol.Optional("events"): list,
        },
        extra=vol.ALLOW_EXTRA,
    ),
    SECTION_REMINDERS: vol.Schema(
        {**_ITEM_BASE, vol.Optional("items"): list}, extra=vol.ALLOW_EXTRA
    ),
    SECTION_NOTES: vol.Schema(
        {**_ITEM_BASE, vol.Optional("notes"): list}, extra=vol.ALLOW_EXTRA
    ),
    SECTION_ALBUMS: vol.All(
        vol.Schema(
            {
                **_ITEM_BASE,
                vol.Optional("slug"): str,
                vol.Optional("kind"): _OPTIONAL_TEXT,
                vol.Optional("count"): vol.Any(None, int),
                vol.Optional("files"): [str],
            },
            extra=vol.ALLOW_EXTRA,
        ),
        _album_has_name,
    ),
}

#: For each section, the key holding nested entries and the schema for each one.
NESTED: dict[str, tuple[str, vol.Schema]] = {
    SECTION_CALENDARS: ("events", EVENT_SCHEMA),
    SECTION_REMINDERS: ("items", REMINDER_SCHEMA),
    SECTION_NOTES: ("notes", NOTE_SCHEMA),
}


@dataclass
class CleanResult:
    """The validated payload and a count of what was skipped, per section."""

    payload: dict[str, Any]
    skipped: dict[str, int] = field(default_factory=dict)

    def note_skip(self, section: str) -> None:
        """Count one skipped item or nested entry against ``section``."""
        self.skipped[section] = self.skipped.get(section, 0) + 1


def _validate_list(
    entries: list[Any],
    schema: Callable[[Any], dict[str, Any]],
    describe: Callable[[int, Any], str],
    on_skip: Callable[[], None],
) -> list[dict[str, Any]]:
    """Return the entries that pass ``schema``; log and count the rest."""
    valid: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        try:
            valid.append(schema(entry))
        except vol.Invalid as err:
            _LOGGER.warning(
                "Skipping %s pushed by the Mac: %s",
                describe(index, entry),
                humanize_error(entry, err)
                if isinstance(entry, dict)
                else "expected an object",
            )
            on_skip()
    return valid


def clean_payload(raw: Any) -> CleanResult:
    """Validate a push body.

    Raises :class:`vol.Invalid` when the envelope is wrong (not an object, a
    section that isn't a list, ...); the caller turns that into a 400.
    Malformed items and nested entries are dropped (and logged) rather than
    raising, see the module docstring.
    """
    payload: dict[str, Any] = PAYLOAD_SCHEMA(raw)
    result = CleanResult(payload=payload)

    for section in SECTIONS:
        items = payload.get(section)
        if items is None:
            continue

        def _skip(section: str = section) -> None:
            result.note_skip(section)

        cleaned = _validate_list(
            items,
            ITEM_SCHEMAS[section],
            lambda index, item, section=section: (
                f"{section} item {item.get('id', f'#{index}')!r}"
                if isinstance(item, dict)
                else f"{section} item #{index}"
            ),
            _skip,
        )

        if section in NESTED:
            key, schema = NESTED[section]
            for item in cleaned:
                if key not in item:
                    continue
                item[key] = _validate_list(
                    item[key],
                    schema,
                    lambda index, _entry, item=item, key=key, section=section: (
                        f"{key[:-1]} #{index} in {section} item {item['id']!r}"
                    ),
                    _skip,
                )
        payload[section] = cleaned

    return result
