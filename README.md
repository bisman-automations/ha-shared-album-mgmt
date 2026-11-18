<p align="center">
  <img src="custom_components/shared_album_mgmt/brand/icon.png" alt="Shared Album Mgmt" width="128">
</p>

# Shared Album Mgmt

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.10%2B-blue.svg)](https://www.home-assistant.io/)
[![GitHub Release](https://img.shields.io/github/v/release/bisman-automations/ha-shared-album-mgmt)](https://github.com/bisman-automations/ha-shared-album-mgmt/releases)
[![Test](https://github.com/bisman-automations/ha-shared-album-mgmt/actions/workflows/test.yml/badge.svg)](https://github.com/bisman-automations/ha-shared-album-mgmt/actions/workflows/test.yml)
[![Validate](https://github.com/bisman-automations/ha-shared-album-mgmt/actions/workflows/validate.yml/badge.svg)](https://github.com/bisman-automations/ha-shared-album-mgmt/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/bisman-automations/ha-shared-album-mgmt)](LICENSE)

Copies the photos and videos of public iCloud shared albums into your Home
Assistant media folder and keeps them in sync, so slideshows, dashboards and
the media browser always show the album as it is now. A sidebar panel shows
every album, its photos and its quarantine, and edits its settings.

No Apple ID, password or two-factor code is ever asked for: it reads only
albums that have **Public Website** turned on, the same way a browser does.

## Requirements

- Home Assistant 2026.10 or newer.
- An iCloud shared album with **Public Website** turned on (in Photos, open
  the shared album, tap the people icon, turn on **Public Website** and copy
  the link). Both `https://photos.icloud.com/shared/album/…` links and older
  `https://www.icloud.com/sharedalbum/#…` links work.
- Shared Photo Libraries (iCloud Shared Photo Library) and albums shared only
  with people are not supported: Apple only offers those with an Apple ID
  sign-in.

## Installation

### Marketplace (Home Assistant 2026.11 and newer, recommended)

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=bisman-automations&repository=ha-shared-album-mgmt&category=integration)

1. Open the Marketplace and search for **Shared Album Mgmt**, or select the button above to open this repository in the Marketplace.
2. Download **Shared Album Mgmt** and restart Home Assistant.

New versions show up under **Settings > Updates**. Already installed Shared
Album Mgmt with HACS? There's nothing to do: Home Assistant moves it into the
Marketplace the first time it starts on 2026.11.

### HACS (Home Assistant 2026.10 and older)

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bisman-automations&repository=ha-shared-album-mgmt&category=integration)

1. Open HACS and search for **Shared Album Mgmt**, or select the button above to open this repository in HACS.
2. Download **Shared Album Mgmt** and restart Home Assistant.

### Custom repository

If **Shared Album Mgmt** does not appear in search:

1. In HACS open the menu, choose **Custom repositories**, and add `https://github.com/bisman-automations/ha-shared-album-mgmt` as an **Integration**.
2. Download **Shared Album Mgmt** and restart Home Assistant.

### Manual

1. Download `shared_album_mgmt.zip` from the [latest release](https://github.com/bisman-automations/ha-shared-album-mgmt/releases/latest).
2. Unzip it into `config/custom_components/shared_album_mgmt/` and restart Home Assistant.

## Setup

[![Open your Home Assistant instance and start setting up Shared Album Mgmt.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=shared_album_mgmt)

Select the button above, or go to **Settings > Devices & services > Add
integration** and search for **Shared Album Mgmt**.

1. Paste the album's public link. The album is read once to check the link
   and to suggest its name.
2. Choose the media folder and folder (default
   `/media/shared_albums/<album name>`), the photo format, what happens when
   a photo leaves the album, and how often to sync.

Add one entry per album. After the first album, the **Shared Album Mgmt**
sidebar panel (admins only) can add more.

The first sync starts in the background right away; Home Assistant doesn't
wait for Apple to finish starting.

## Settings

Every setting can be changed from the integration's **Configure** dialog or
from the album's **Settings** tab in the sidebar. Saving reloads the album.

| Setting | Default | What it does |
| --- | --- | --- |
| Sync every | 180 minutes | 15 minutes to 7 days, or 0 for manual only (Sync now button or action). |
| Photos / Videos | both on | What to copy. |
| Photo format | Convert HEIC to JPEG | **Convert HEIC to JPEG** takes the largest version and turns HEIC into JPEG (upright, EXIF and colour profile kept). **Keep originals as-is** takes the largest version exactly as Apple stores it (HEIC stays HEIC). **Apple's smaller JPEG** takes Apple's ~2048 px JPEG (and medium video), much smaller files for dashboards; when Apple only keeps the original (common for shared albums) it takes that, converting HEIC to JPEG. |
| When a photo leaves the album | Quarantine | **Quarantine** moves the file to a hidden `.quarantine` folder where you can restore or delete it. **Keep** leaves it in place. **Delete** removes it. |
| Media folder / Folder | `local` / `shared_albums/<slug>` | Where the files go. The folder must stay inside the media folder. |
| Keep days | 0 (all) | Only copy items taken in the last N days. |
| Max files | 0 (all) | Only the newest N. |
| Minimum file size / Minimum long edge | 0 | Skip renditions smaller than this. |
| Write latest.jpg / Write index.json | on | See [Files](#files). |
| Extra trusted hosts | none | See [Trusted hosts](#trusted-hosts). |
| Downloads at once | 3 | 1 to 8. |
| Keep this much disk free | 500 MB | A sync that would leave less free space stops before downloading. |
| JPEG quality | 90 | For HEIC conversion. |

Lowering a limit (or turning videos off) deletes the local copies the album
no longer wants, but only files still in the album and still exactly as
downloaded.

### Quarantine safety

Removing files is where a sync can do damage, so these rules always apply,
whichever mode you choose:

- Nothing counts as having left the album until one complete listing of it
  has been read (the baseline).
- An empty listing from Apple never removes anything.
- A listing that stops part way (paging stops, item counts don't match)
  fails the sync instead of being treated as the album.
- If more than half the album (and at least 10 items) vanish at once, nothing
  happens until the next sync sees the same thing.
- A file is moved or deleted only if it still has exactly the bytes that were
  downloaded (SHA-256). A file you edited or replaced is left alone.
- Files you restore from quarantine are kept for good and never removed by a
  later sync.

## The sidebar panel

**Shared Album Mgmt** in the sidebar (admins only) has a tab per album with:

- Status: last sync, item counts, space used, a progress bar while syncing,
  errors and notes, **Sync now**, **Check every file** (re-reads every file
  and downloads again any that changed), **Open in Media** and **Remove**.
- **Photos**: a thumbnail grid of the files on disk, with a filter for photos
  or videos and a full-size preview.
- **Quarantine**: files that left the album; select them to restore or delete.
- **Settings**: every setting above.
- **Add album**: paste a link, preview the album, and add it.

Removing an album keeps its folder and files; delete them from the media
browser if you no longer want them.

## Entities

Each album is a device with:

| Entity | Notes |
| --- | --- |
| Status | Idle, Syncing or Error. |
| Last sync | When the last successful sync finished. Its attributes hold the last run's counts. |
| Items | Files on disk. |
| Space used | Size of those files. |
| Quarantined | Diagnostic. |
| Last error | Why the last sync failed, or None. |
| Problem | On when the last sync failed or some downloads failed. |
| Sync now | Button. |
| Latest photo | Image entity with the newest photo. |

Errors show on these entities instead of making them unavailable.

## Actions

| Action | Fields |
| --- | --- |
| `shared_album_mgmt.sync_now` | `config_entry_id`, optional `full` (check every file). |
| `shared_album_mgmt.rebuild_index` | `config_entry_id`. Forgets files deleted by hand and rewrites `index.json` and `latest.jpg` without contacting Apple. Returns `forgotten` and `items`. |
| `shared_album_mgmt.purge_quarantine` | `config_entry_id`, optional `older_than_days`. Returns `deleted`. |

## Files

Each album folder holds the photos and videos plus:

- `latest.jpg`: a copy of the newest photo (JPEG or PNG).
- `index.json`: every file, newest first, in a version 2 format that
  works with existing shared-album cards and scripts. It adds
  `media_content_id`, `in_album` and `sha256` to each item.
- `.quarantine/`: quarantined files (hidden from the media browser).

The parent folder gets `albums.json`, listing the albums saved under it.

## Trusted hosts

The album's link names the album, but Apple answers from other hosts, such
as a numbered CloudKit partition (`p51-ckdatabasews.icloud.com`). Every host
Apple sends the integration to is checked before it is contacted, and only
HTTPS is used:

- CloudKit: `ckdatabasews.icloud.com`, `pNN-ckdatabasews.icloud.com`, and
  one subdomain level of `ckdatabasews.icloud.com` (plus `.com.cn`).
- Older albums: the same shapes of `sharedstreams.icloud.com`.
- Downloads: subdomains of `icloud-content.com` (plus `.com.cn`), checked
  again on every redirect.

If Apple
starts using a host outside these lists, the sync stops with an error naming
the host and a Repairs issue that adds it to the album's **Extra trusted
hosts** when you confirm. You can also add hosts there yourself (`*.example.com`
matches subdomains), from the setup dialog's **Advanced** section, or with
**Trust** in the panel's add form.

## Privacy

The album link works like a password for the album, so it is stored only in
the config entry, never logged, and redacted from diagnostics. Photos are
sent only from Apple to your Home Assistant.

## Troubleshooting

- **"Apple returned an unexpected … host":** see [Trusted hosts](#trusted-hosts).
- **"This album is shared with people only":** turn on **Public Website** for
  the album in Photos.
- **HEIC photos saved as Apple's JPEG:** pillow-heif couldn't load on your
  system; a Repairs issue says so. Everything else keeps working.
- **Nothing was removed:** see [Quarantine safety](#quarantine-safety); the
  panel shows the reason.
- **Diagnostics:** on the integration's page, open the menu and choose
  **Download diagnostics**. Attach the file to an issue (check it first for
  anything you'd rather not share).
- **Debug logs:** on the integration's page choose **Enable debug logging**,
  reproduce the problem, then **Disable debug logging** to download the log.
- Report problems at [Issues](https://github.com/bisman-automations/ha-shared-album-mgmt/issues).

## Development

```
python3.14 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
ruff check . && ruff format --check .
mypy custom_components/shared_album_mgmt
pytest
npm ci && npm test        # panel logic (Node)
npm run build             # after changing frontend/
```

CI also tests the oldest supported Home Assistant (`requirements_test_min.txt`)
and runs hassfest and the HACS checks. Releases are drafted automatically from
`CHANGELOG.md` on every push to `main` and published by hand. See
[CLAUDE.md](CLAUDE.md) and [CONTRIBUTING](https://github.com/bisman-automations/.github/blob/main/CONTRIBUTING.md).

## Credits

Inspired by [iCloud Shared Album Sync](https://github.com/BZPJoe/icloud-shared-album-sync-repo)
by BZPJoe (MIT License), a Home Assistant app that syncs public shared albums.
This integration is written from scratch, but follows its approach to Apple's
public album endpoints, its `index.json`/`latest.jpg` format, and the
partition-host fix from its PR #3.

## License

[MIT](LICENSE)
