# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.3] - 2026-11-22

### Fixed

- **Album counts update as photos arrive.** Each album's sensor now goes up as soon as a photo is uploaded. Before, it stayed at the old number until the next sync, so a new album showed 0 photos after its photos were already in Home Assistant.

### Changed

- **Less work on each sync.** A calendar, reminders list, notes folder or album that didn't change in a sync is no longer rewritten in Home Assistant, and the Last sync sensor is only written when the sync time changes. Nothing changes in what you see.

## [1.1.2] - 2026-11-21

### Changed

- **Ruff 0.17.6.** Linting uses the current Ruff release. Nothing changes for you.

## [1.1.1] - 2026-11-17

### Fixed

- **A bad push is turned away instead of failing.** A push that isn't a JSON object, such as a list, or has a section that isn't a list, now gets a clear 400 answer and changes nothing. Before, Home Assistant hit an error and answered 500. Raised in the review for the default HACS list.
- **One odd item no longer stops a push.** An album with no title or slug, an item without an id, or an event, reminder or note with the wrong kind of value is skipped and logged as a warning. Everything else in the push is still saved. The answer lists how many were skipped in each section.

### Changed

- Ruff 0.17.5 for the lint checks.

## [1.1.0] - 2026-11-13

### Changed

- **Needs Home Assistant 2026.3 or newer.** That's the first release that shows an integration's own icon, so Mac Sync's icon now appears in Home Assistant and the Marketplace. Older Home Assistant versions stay on Mac Sync 1.0.3.

## [1.0.3] - 2026-11-13

### Changed

- **Shown as a device.** Home Assistant now lists Mac Sync as a device: your Mac.
- **Tidier setup.** Mac Sync keeps its data with its own entry, as Home Assistant recommends. Nothing changes for you.
- **Smoother updates.** Each kind of entity now tells Home Assistant how many updates it can take at once, as Home Assistant recommends. Nothing changes in how anything looks or works.

## [1.0.2] - 2026-11-11

### Added

- A dark-theme icon for the Mac Sync page. It is the same artwork, which is
  already a solid tile, so it reads on a dark background.

### Changed

- The README now matches the Mac app and the Mac Sync integration: macOS 14,
  Home Assistant 2024.6 or newer, Marketplace and HACS install, every
  setting, what shows up in Home Assistant, and troubleshooting.
- The setup step names the menu bar app HA Sync.
- Tests and CI follow the shared bisman-automations workflows. Ruff is
  0.17.4. The oldest Home Assistant exercised in CI is still 2024.6.

## [1.0.1] - 2026-11-09

### Fixed

- Unchecking a calendar, Reminders list, Notes folder or photo album on the
  Mac now makes its Home Assistant entity unavailable in a way you can
  delete it. Before, it went unavailable but Home Assistant wouldn't offer
  Delete, because the integration still provided it. Checking it again
  brings back the same entity with the same entity ID.
- The Mac app now syncs about 3 seconds after you check or uncheck
  something in Settings, instead of at the next scheduled sync.

## [1.0.0] - 2026-11-09

### Added

- **HA Sync for macOS**: a menu bar app that sends the Calendar calendars,
  Reminders lists, Photos albums (including iCloud Shared Albums and smart
  albums) and Notes folders you choose to Home Assistant. It syncs on a
  timer and within about 10 seconds of a Calendar or Reminders change. It
  runs on Apple silicon and Intel Macs (macOS 14 or later).
- **Mac Sync integration**: creates a calendar entity for each calendar, a
  to-do list for each Reminders list, a sensor for each Notes folder and for
  each photo album, and a last-sync sensor. Photos are saved to
  `/media/mac_sync/<album>/`.

[1.1.3]: https://github.com/bisman-automations/ha-sync/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/bisman-automations/ha-sync/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/bisman-automations/ha-sync/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/bisman-automations/ha-sync/compare/v1.0.3...v1.1.0
[1.0.3]: https://github.com/bisman-automations/ha-sync/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/bisman-automations/ha-sync/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/bisman-automations/ha-sync/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/bisman-automations/ha-sync/releases/tag/v1.0.0
