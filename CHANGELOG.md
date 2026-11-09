# Changelog

All notable changes to this project are documented here. Each release's
section becomes its GitHub release notes.

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
