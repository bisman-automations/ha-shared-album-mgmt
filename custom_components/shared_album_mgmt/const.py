"""Constants for Shared Album Mgmt.

Every option key, default and limit lives here so the config flow, the
options flow, the sidebar panel's websocket commands and the sync engine all
agree on one definition.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

DOMAIN: Final = "shared_album_mgmt"
NAME: Final = "Shared Album Mgmt"

# --- Config entry data (what the album is) --------------------------------

CONF_URL: Final = "url"
CONF_KIND: Final = "kind"
CONF_ALBUM_ID: Final = "album_id"
CONF_NAME: Final = "name"


class LinkKind(StrEnum):
    """Which of Apple's two public-link styles an album uses."""

    # https://photos.icloud.com/shared/album/<id> (public CloudKit)
    MODERN = "modern"
    # https://www.icloud.com/sharedalbum/#<id> (the sharedstreams web API)
    LEGACY = "legacy"


# --- Options (how the album is synced) ------------------------------------

CONF_INTERVAL: Final = "interval_minutes"
CONF_SYNC_PHOTOS: Final = "sync_photos"
CONF_SYNC_VIDEOS: Final = "sync_videos"
CONF_PHOTO_FORMAT: Final = "photo_format"
CONF_LEAVE_MODE: Final = "leave_mode"
CONF_MEDIA_DIR: Final = "media_dir"
CONF_FOLDER: Final = "folder"
CONF_KEEP_DAYS: Final = "keep_days"
CONF_MAX_FILES: Final = "max_files"
CONF_MIN_SIZE_KB: Final = "min_file_size_kb"
CONF_MIN_LONG_EDGE: Final = "min_long_edge"
CONF_WRITE_LATEST: Final = "write_latest"
CONF_WRITE_INDEX: Final = "write_index"
CONF_EXTRA_HOSTS: Final = "extra_trusted_hosts"
CONF_CONCURRENCY: Final = "max_concurrent_downloads"
CONF_MIN_FREE_MB: Final = "min_free_space_mb"
CONF_JPEG_QUALITY: Final = "jpeg_quality"

# Options-flow sections. Stored options are flat; sections only group the form.
SECTION_SCHEDULE: Final = "schedule"
SECTION_CONTENT: Final = "content"
SECTION_STORAGE: Final = "storage"
SECTION_LIMITS: Final = "limits"
SECTION_ADVANCED: Final = "advanced"


class PhotoFormat(StrEnum):
    """What to save for a photo."""

    # Largest original; HEIC/HEIF is converted to JPEG locally (pillow-heif).
    CONVERT = "convert"
    # Largest original exactly as Apple stores it (HEIC stays HEIC).
    ORIGINAL = "original"
    # Apple's own medium JPEG, sized for dashboards and slideshows.
    DASHBOARD = "dashboard"


class LeaveMode(StrEnum):
    """What happens to a local file when its photo leaves the album."""

    QUARANTINE = "quarantine"
    KEEP = "keep"
    DELETE = "delete"


DEFAULT_INTERVAL: Final = 180  # minutes; 0 means manual only
DEFAULT_PHOTO_FORMAT: Final = PhotoFormat.CONVERT
DEFAULT_LEAVE_MODE: Final = LeaveMode.QUARANTINE
DEFAULT_MEDIA_DIR: Final = "local"
DEFAULT_FOLDER_ROOT: Final = "shared_albums"
DEFAULT_CONCURRENCY: Final = 3
DEFAULT_MIN_FREE_MB: Final = 500
DEFAULT_JPEG_QUALITY: Final = 90

MIN_INTERVAL: Final = 15
MAX_INTERVAL: Final = 10080  # one week
MAX_CONCURRENCY: Final = 8

# --- Files written next to the media ---------------------------------------

INDEX_FILENAME: Final = "index.json"
LATEST_FILENAME: Final = "latest.jpg"
CATALOG_FILENAME: Final = "albums.json"
QUARANTINE_DIR: Final = ".quarantine"
TEMP_SUFFIX: Final = ".partial"
# Names the engine owns inside an album folder. Anything else is user data
# and is never touched unless the store says this integration wrote it.
RESERVED_NAMES: Final = frozenset(
    {INDEX_FILENAME, LATEST_FILENAME, CATALOG_FILENAME, QUARANTINE_DIR}
)

# --- Network ---------------------------------------------------------------

REQUEST_TIMEOUT: Final = 40  # seconds, per Apple API request
DOWNLOAD_TIMEOUT: Final = 600  # seconds, per file
DOWNLOAD_CHUNK: Final = 1024 * 1024
MAX_ATTEMPTS: Final = 3
BACKOFF_SECONDS: Final = 2.0
USER_AGENT: Final = "HomeAssistant-SharedAlbumMgmt"

# A sync where more than this share of tracked items vanished at once (and at
# least MASS_REMOVAL_MIN items) is held until a second listing agrees.
MASS_REMOVAL_RATIO: Final = 0.5
MASS_REMOVAL_MIN: Final = 10

# --- Storage, signals, panel ----------------------------------------------

STORAGE_VERSION: Final = 1
STORAGE_SAVE_DELAY: Final = 5
SIGNAL_UPDATED: Final = f"{DOMAIN}_updated"

PANEL_URL: Final = "shared-album-mgmt"
PANEL_TITLE: Final = NAME
PANEL_ICON: Final = "mdi:image-multiple"
PANEL_ELEMENT: Final = "shared-album-mgmt-panel"
PANEL_JS_URL: Final = f"/{DOMAIN}_static/shared-album-mgmt-panel.js"
THUMB_URL: Final = f"/api/{DOMAIN}/thumb"
THUMB_SIZE: Final = 320
SIGNED_PATH_SECONDS: Final = 3600

# --- Services --------------------------------------------------------------

SERVICE_SYNC_NOW: Final = "sync_now"
SERVICE_REBUILD_INDEX: Final = "rebuild_index"
SERVICE_PURGE_QUARANTINE: Final = "purge_quarantine"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
ATTR_FULL: Final = "full"
ATTR_OLDER_THAN_DAYS: Final = "older_than_days"

# --- Repairs ---------------------------------------------------------------

ISSUE_UNTRUSTED_HOST: Final = "untrusted_host"
ISSUE_HEIC_UNAVAILABLE: Final = "heic_unavailable"
ISSUE_LOW_DISK: Final = "low_disk_space"
ISSUE_ALBUM_GONE: Final = "album_gone"
