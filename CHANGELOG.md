# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-11-19

### Fixed

- Confirming the album folder no longer blocks the event loop. `Path.resolve()`
  (which follows symlinks so a folder cannot write outside the media
  directory) runs in the executor during setup, together with loading the
  album's store, and the same check is used when the options flow, the setup
  dialog or the sidebar panel saves settings. Tests now watch `Path.resolve`
  so a later regression fails CI.

### Changed

- Shared Album Mgmt is in the HACS default store. The README's Marketplace
  and HACS sections say you can search for it without adding a custom
  repository; the custom repository steps stay as a fallback.
- Ruff 0.17.6, up from 0.17.5. The newest Home Assistant test harness is
  still 2026.10.4, and the 2026.10 minimum stays on its current pin.

## [0.1.0] - 2026-11-18

### Added

- First release: sync public iCloud shared albums (`photos.icloud.com/shared/album/…`
  and older `icloud.com/sharedalbum/#…` links) into a Home Assistant media
  folder, one config entry per album, no Apple ID needed.
- Photo format per album: convert HEIC to JPEG (largest version), keep
  originals as-is (largest version), or Apple's smaller JPEG.
- When a photo leaves the album: quarantine (restore or delete later), keep,
  or delete, with baseline, empty-listing, partial-listing, mass-removal and
  unchanged-file safety checks.
- Trusted-host allow-list for CloudKit partition (`pNN-ckdatabasews`),
  shared-streams and download hosts, extra trusted hosts per album, and a
  Repairs issue that trusts a new host.
- Sidebar panel for admins: album tabs with status and progress, a photo
  grid, quarantine review, settings, and adding albums.
- Sensors (status, last sync, items, space used, quarantined, last error), a
  problem binary sensor, a Sync now button and a latest-photo image entity.
- Actions: `sync_now`, `rebuild_index` and `purge_quarantine`.
- `index.json` and `latest.jpg` compatible with iCloud Shared Album Sync, and
  an `albums.json` catalog.
- Diagnostics with the album link and id redacted.
- Checked against a live public album: links are matched without regard to
  case in the scheme and host (`Https://…`), partition hosts with an explicit
  `:443` port are trusted, the album name is read from the share record's
  `cloudkit.title`, Apple's `Signature: …` data in the description field is
  not shown as a caption, and Apple's smaller JPEG falls back to the original
  (HEIC converted to JPEG) when Apple keeps no smaller JPEG. Modern links
  carry no contributor, so that field stays empty for them. Sanitized
  recorded responses are part of the tests.

[0.1.1]: https://github.com/bisman-automations/ha-shared-album-mgmt/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/bisman-automations/ha-shared-album-mgmt/releases/tag/v0.1.0
