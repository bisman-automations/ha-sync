# Changelog

All notable changes to this project are documented here. Each release's
section becomes its GitHub release notes.

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
