<p align="center">
  <img src="https://raw.githubusercontent.com/bisman-automations/ha-sync/main/custom_components/mac_sync/brand/icon.png" alt="HA Sync icon" width="128">
</p>

# HA Sync

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.6%2B-blue.svg)](https://www.home-assistant.io/)
[![GitHub Release](https://img.shields.io/github/v/release/bisman-automations/ha-sync)](https://github.com/bisman-automations/ha-sync/releases)
[![Test](https://github.com/bisman-automations/ha-sync/actions/workflows/test.yml/badge.svg)](https://github.com/bisman-automations/ha-sync/actions/workflows/test.yml)
[![Validate](https://github.com/bisman-automations/ha-sync/actions/workflows/validate.yml/badge.svg)](https://github.com/bisman-automations/ha-sync/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/bisman-automations/ha-sync)](LICENSE)

HA Sync sends the calendars, reminders, notes and photos you choose on a Mac to Home Assistant. It is two parts:

| Part | Where | What it does |
| --- | --- | --- |
| **HA Sync** | `mac/` | Menu bar app for macOS 14 or later (Apple silicon and Intel). Reads the Calendar calendars, Reminders lists, Photos albums and Notes folders you tick, and pushes them to Home Assistant. |
| **Mac Sync** | `custom_components/mac_sync/` | Home Assistant integration. Receives that push and creates one device, named after the Mac, with a calendar, to-do list or sensor for each item. |

Sync is one way, Mac to Home Assistant. Nothing you change in Home Assistant is written back to Calendar, Reminders, Notes or Photos.

## Requirements

- Home Assistant 2024.6 or newer.
- The Mac Sync integration installed and added (see below). Photos need Home Assistant's media folder, which is included with Home Assistant.
- An administrator long-lived access token. A token for a user who is not an administrator is rejected.
- For the app: macOS 14 or later. Building it yourself also needs Xcode or the Command Line Tools, and `python3`.

## Installation

Install **Mac Sync** in Home Assistant first, then install the **HA Sync** app on the Mac.

### Marketplace (Home Assistant 2026.11 and newer, recommended)

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=bisman-automations&repository=ha-sync&category=integration)

1. Open the Marketplace and search for **Mac Sync**, or select the button above to open this repository in the Marketplace.
2. Download **Mac Sync** and restart Home Assistant.

New versions show up under **Settings → Updates**. Already installed Mac Sync with HACS? There's nothing to do: Home Assistant moves it into the Marketplace the first time it starts on 2026.11.

### HACS (Home Assistant 2026.10 and older)

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bisman-automations&repository=ha-sync&category=integration)

1. Open HACS and search for **Mac Sync**, or select the button above to open this repository in HACS.
2. Download **Mac Sync** and restart Home Assistant.

Mac Sync is not in the default HACS catalog yet, so search may not find it. Use **Custom repository** below.

### Custom repository

If **Mac Sync** does not appear in search:

1. In HACS open the menu, choose **Custom repositories**, and add `https://github.com/bisman-automations/ha-sync` as an **Integration**.
2. Download **Mac Sync** and restart Home Assistant.

### Manual

Download `mac_sync.zip` from the [latest release](https://github.com/bisman-automations/ha-sync/releases/latest), unzip it into `config/custom_components/mac_sync/`, and restart Home Assistant.

### Mac app

Download `HA-Sync.zip` from the [latest release](https://github.com/bisman-automations/ha-sync/releases/latest), unzip it, and move **HA Sync** to Applications.

The app is signed, notarized and stapled when the release was built with an Apple Developer ID. Otherwise it is ad-hoc signed: the first time you open it, right-click **HA Sync** and choose **Open**.

To build it yourself, from a checkout of this repository:

```bash
cd mac
./build.sh
cp -R "build/HA Sync.app" /Applications/
```

`build.sh` reads the version from Mac Sync's manifest, builds a universal binary (Apple silicon and Intel) and signs the app. Pass `SIGN_IDENTITY="Developer ID Application: Name (TEAMID)"` to sign with a Developer ID instead of the ad-hoc signature. There is no Homebrew formula.

## Setup

[![Open your Home Assistant instance and start setting up a new instance of Mac Sync.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=mac_sync)

1. Go to **Settings → Devices & services → Add integration → Mac Sync**. There is nothing to fill in. Only one Mac Sync entry is allowed.
2. On the administrator account, open your profile and go to **Security → Long-lived access tokens → Create token**. Copy the token. Home Assistant shows it only once.
3. Open **HA Sync**. It has no Dock icon. Click the house icon in the menu bar and choose **Settings…**.
4. On the **Home Assistant** tab, enter the URL (the default is `http://homeassistant.local:8123`) and the token, then click **Test Connection**. A successful check names the Mac Sync version it found. Turn on **Launch at login** if you want the app to start with the Mac. Put the app in Applications first.
5. On **Calendar**, **Reminders** and **Photos**, click **Grant Access**, then tick what should sync.
6. On **Notes**, click **Load Folders from Notes**, approve the prompt that asks to control Notes, then tick folders.
7. Click **Sync Now**. The menu shows progress, then the time of the last sync. Warnings stay in the menu until the next successful sync with no errors.

## What shows up in Home Assistant

Everything is on one device. Its name is the Mac's sharing name, the manufacturer is Apple, and the model is macOS (Mac Sync).

| Source on the Mac | Entity | State | Attributes |
| --- | --- | --- | --- |
| Each ticked calendar | Calendar | The next event | `color` (hex) and `account`. Events have a title, start, end, all-day flag, location and notes. Use them on the Calendar dashboard, in automations, and with `calendar.get_events`. |
| Each ticked Reminders list | To-do list | The items on that list | Each item has a title, completed or not, an optional due date or time, and notes. Read-only. |
| Each ticked Notes folder | Sensor | How many notes are in the folder | `account`, and `notes`: each note's title, plain-text body and modified time. The note text is not written to recorder history. |
| Each ticked Photos album | Sensor | How many photos from that album are stored in Home Assistant | `kind` (My Albums, Shared Albums or Smart Albums), `album_count` (how many photos are in the album on the Mac), `folder` and `media_content_id`. |
| Every successful push | Sensor, **Last sync** | When the last push was accepted | Diagnostic. |

Calendars and to-do lists are read-only. Home Assistant does not offer to add or edit events or reminders.

Photos are JPEGs with location and other metadata removed. They are stored in `/media/mac_sync/<album>/`. Browse them in **Media → My media → mac_sync**, or use the folder in a slideshow card or a picture-frame integration. `media_content_id` is `media-source://media_source/local/mac_sync/<album>`.

When a photo leaves an album, its file is deleted. When a photo is edited, the new version replaces the old file. Deselecting an album deletes that album's folder.

Deselecting a calendar, list, folder or album removes its entity from what Mac Sync provides. Home Assistant keeps the entity registry entry and shows the entity as unavailable, which is what lets you delete it. Select it again and the same entity comes back. An empty selection sends an empty list. A section the app could not read (permission denied, for example) is left out of the push, and Home Assistant keeps the previous entities for that section.

Every accepted push fires a `mac_sync_updated` event. `source` is the Mac's name.

```yaml
triggers:
  - trigger: event
    event_type: mac_sync_updated
actions:
  - action: notify.persistent_notification
    data:
      message: "{{ trigger.event.data.source }} synced."
```

## Settings

The app saves the URL, the ticked items and these settings on the Mac. The token is stored in the Keychain, not in a preferences file.

| Setting | Tab | Default | What it does |
| --- | --- | --- | --- |
| URL | Home Assistant | `http://homeassistant.local:8123` | Home Assistant's address. A trailing slash is ignored. `http` and `https` are accepted. |
| Long-lived access token | Home Assistant | empty | Administrator token. **Test Connection** checks the URL, the token and that Mac Sync is added. |
| Sync every | Home Assistant | 15 min | How often a full sync runs. Choices: 5, 15, 30, 60 or 180 minutes. The first sync runs about 5 seconds after launch. |
| Launch at login | Home Assistant | off | Starts HA Sync when you log in. |
| Past days | Calendar | 7 | How many days of past events to send (0–365). The same number is the window for completed reminders. |
| Future days | Calendar | 60 | How many days of upcoming events to send (1–730). |
| Include reminders completed in the last N days | Reminders | off | N is **Past days**. Incomplete reminders are always sent. |
| Newest photos per album | Photos | 300 | Caps how many of the newest photos are synced. Choices: 50, 100, 300, 1000 or 5000. |
| Max size | Photos | 2048 px | Longest side of the JPEG Home Assistant stores. Choices: 1280, 1920, 2048, 3072 or 4096. |
| Max characters per note | Notes | 2000 | Body length sent for each note (200–20000, in steps of 200). Longer notes are cut and end with an ellipsis. |

Calendar and Reminders also sync about 10 seconds after a change in those apps. Ticking or unticking anything in Settings syncs about 3 seconds later, so an item you clear goes unavailable in Home Assistant without waiting for the timer. Several quick ticks become one sync. A tick on the Photos tab includes photos. A tick on another tab does not re-upload photos.

**Sync Now** in the menu or on the Home Assistant tab always includes photos.

## Calendars, reminders, photos and notes

**Calendars.** Each ticked calendar becomes one calendar entity. All-day events use a date. Timed events use a local date and time. Event notes are cut at 2000 characters. The entity's state is the event that is on now, or the next one.

**Reminders.** Each ticked list becomes one to-do list. A reminder with a date but no time is an all-day due date. Reminder notes are cut at 2000 characters.

**Photos.** The list includes your albums, iCloud Shared Albums and smart albums. An empty smart album is not listed. Videos are skipped. A Live Photo is synced as its still image. The first sync of a shared album downloads the originals from iCloud, which can take a while for a large album. Lower **Newest photos per album** to cap that. **Refresh** reloads the album list. Limited Photos access is enough: only the photos you allowed are visible to the app.

**Notes.** Notes has no public API, so the app reads it with AppleScript. Folders are listed per account, and a folder inside another is shown as `Parent / Child`. The body is plain text. When the first line repeats the title, that line is dropped. A locked note is sent with an empty body. Click **Load Folders from Notes** again after you add a folder.

## Push API

Anything that can make an HTTPS request can push the same payload the app does. Both endpoints need `Authorization: Bearer <admin long-lived token>`.

- `GET /api/mac_sync/push` returns `{"ok": true, "version": "1.0.2"}` when Mac Sync is set up. `ok` is false when the integration is installed but not added. `version` is the installed Mac Sync version.
- `POST /api/mac_sync/push` takes JSON:

```json
{
  "source": "Office Mac",
  "calendars": [],
  "reminders": [],
  "notes": [],
  "albums": []
}
```

Leave a section out to keep what Home Assistant already has. Send an empty list to clear that section. The response is `{"ok": true, "missing": {"<album-slug>": ["file.jpg"]}}`. `missing` lists photo files that were named in an album but are not on disk yet.

- `POST /api/mac_sync/photo` is multipart form data with the fields `album` (the album slug), `filename` and `file` (the JPEG).

A push that is not JSON, or a photo upload missing a field, is rejected. A token that is not an administrator's gets 401.

## Troubleshooting

The menu bar is the error list. Each line is the reason the last sync gave.

- **Set your Home Assistant URL and token in Settings.** The URL or the token is empty, or the URL does not start with `http://` or `https://`.
- **Home Assistant rejected the token (401).** Create a new long-lived token while logged in as an administrator. A token from a non-admin user is not accepted for a push.
- **Mac Sync endpoint not found (404).** Mac Sync is not installed, or Home Assistant was not restarted after the files were copied. Install it, restart, then add it.
- **The mac_sync integration is installed but not added.** Add **Mac Sync** under **Settings → Devices & services**.
- **Home Assistant returned 503, or the Mac cannot connect.** The Mac has to reach the URL you entered. Check the host, the port and that a private HTTPS certificate is trusted on the Mac.
- **Calendar access not granted / Reminders access not granted / Photos access not granted.** Use **Grant Access** on that tab. If macOS does not ask again, allow HA Sync under **System Settings → Privacy & Security** for Calendars, Reminders or Photos. Rebuilding the app changes its signature, and macOS may ask for permission again.
- **Notes access denied.** Allow HA Sync under **System Settings → Privacy & Security → Automation → Notes**, then click **Load Folders from Notes** again.
- **Some photos failed to upload.** The menu says how many. The next sync retries the ones Home Assistant still does not have. A shared album's first sync downloads from iCloud before it can upload.
- **An entity stayed after you unticked it.** It is unavailable on purpose, so you can delete it on the device page. Tick it again to bring the same entity back. Its photo folder, if it was an album, is already removed.
- **Unticking did not remove anything.** The app only clears a section it could read. If permission was revoked, that section is skipped and the old entities stay.
- **Notes are missing their text.** The note is locked, or the body was longer than **Max characters per note**.
- **A video or a Live Photo's video half is missing.** Videos are not synced. A Live Photo syncs as the still image.

For debug logs, on the Mac Sync page choose **Enable debug logging**, reproduce the problem, then **Disable debug logging** to download the log. Or add this to `configuration.yaml` and restart:

```yaml
logger:
  logs:
    custom_components.mac_sync: debug
```

The app's own errors are the lines in the menu, not that log. Report problems at [Issues](https://github.com/bisman-automations/ha-sync/issues) with the Home Assistant version, the Mac Sync version from **Test Connection**, the macOS version, and the menu text.

## Development

```bash
python3.14 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
ruff check . && ruff format --check .
pytest
```

Home Assistant 2024.6, the oldest version Mac Sync supports, is tested with Python 3.12 and `requirements_test_min.txt`. CI runs the same checks on every push and pull request, on both Home Assistant versions, plus hassfest, HACS validation and the shared repo standards, using the workflows in [bisman-automations/.github](https://github.com/bisman-automations/.github).

The icon is drawn by `swift assets/logo.swift assets/logo.png` on a Mac. The app icon and the integration brand images are made from that file.

Releases are drafted from [CHANGELOG.md](CHANGELOG.md) on every push to `main`. The draft gets `mac_sync.zip` and `HA-Sync.zip` (the Mac app, built on a macOS runner at the same version). Publishing the draft is manual and creates the tag. See [CLAUDE.md](CLAUDE.md) and [CONTRIBUTING](https://github.com/bisman-automations/.github/blob/main/CONTRIBUTING.md).

## License

[MIT](LICENSE)
