"""Album options: defaults, validation and where files go.

Shared by the options flow and the sidebar panel's settings form, so both
accept exactly the same values and show the same errors.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path, PurePosixPath
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from .const import (
    CONF_CONCURRENCY,
    CONF_EXTRA_HOSTS,
    CONF_FOLDER,
    CONF_INTERVAL,
    CONF_JPEG_QUALITY,
    CONF_KEEP_DAYS,
    CONF_LEAVE_MODE,
    CONF_MAX_FILES,
    CONF_MEDIA_DIR,
    CONF_MIN_FREE_MB,
    CONF_MIN_LONG_EDGE,
    CONF_MIN_SIZE_KB,
    CONF_PHOTO_FORMAT,
    CONF_SYNC_PHOTOS,
    CONF_SYNC_VIDEOS,
    CONF_WRITE_INDEX,
    CONF_WRITE_LATEST,
    DEFAULT_CONCURRENCY,
    DEFAULT_FOLDER_ROOT,
    DEFAULT_INTERVAL,
    DEFAULT_JPEG_QUALITY,
    DEFAULT_LEAVE_MODE,
    DEFAULT_MEDIA_DIR,
    DEFAULT_MIN_FREE_MB,
    DEFAULT_PHOTO_FORMAT,
    MAX_CONCURRENCY,
    MAX_INTERVAL,
    MIN_INTERVAL,
    LeaveMode,
    PhotoFormat,
)
from .hosts import normalize_extra_host

_FOLDER_PART = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _.-]*")


def folder_for(title: str) -> str:
    """Default folder for an album title: ``shared_albums/<slug>``."""
    return f"{DEFAULT_FOLDER_ROOT}/{slugify(title) or 'album'}"


def default_media_dir(hass: HomeAssistant) -> str:
    """``local`` when configured, else the first media directory."""
    dirs = hass.config.media_dirs
    if DEFAULT_MEDIA_DIR in dirs or not dirs:
        return DEFAULT_MEDIA_DIR
    return next(iter(dirs))


def default_options(hass: HomeAssistant, title: str) -> dict[str, Any]:
    """Options for a new album."""
    return {
        CONF_INTERVAL: DEFAULT_INTERVAL,
        CONF_SYNC_PHOTOS: True,
        CONF_SYNC_VIDEOS: True,
        CONF_PHOTO_FORMAT: DEFAULT_PHOTO_FORMAT.value,
        CONF_LEAVE_MODE: DEFAULT_LEAVE_MODE.value,
        CONF_MEDIA_DIR: default_media_dir(hass),
        CONF_FOLDER: folder_for(title),
        CONF_KEEP_DAYS: 0,
        CONF_MAX_FILES: 0,
        CONF_MIN_SIZE_KB: 0,
        CONF_MIN_LONG_EDGE: 0,
        CONF_WRITE_LATEST: True,
        CONF_WRITE_INDEX: True,
        CONF_EXTRA_HOSTS: [],
        CONF_CONCURRENCY: DEFAULT_CONCURRENCY,
        CONF_MIN_FREE_MB: DEFAULT_MIN_FREE_MB,
        CONF_JPEG_QUALITY: DEFAULT_JPEG_QUALITY,
    }


def with_defaults(
    hass: HomeAssistant, title: str, options: Mapping[str, Any]
) -> dict[str, Any]:
    """Stored options with any missing key filled from the defaults."""
    return {**default_options(hass, title), **options}


def clean_folder(value: str) -> str | None:
    """Normalise a folder relative to a media directory, or None if unsafe.

    Every part must start with a letter or digit, so ``..``, hidden folders
    and absolute paths are refused and files can't land outside the media
    directory.
    """
    text = str(value or "").strip().strip("/").replace("\\", "/")
    if not text:
        return None
    parts = [p.strip() for p in PurePosixPath(text).parts]
    if not parts or any(not _FOLDER_PART.fullmatch(p) for p in parts):
        return None
    return "/".join(parts)


def resolve_target(hass: HomeAssistant, options: Mapping[str, Any]) -> Path:
    """The album folder on disk. Raises ValueError when it isn't usable."""
    dirs = hass.config.media_dirs
    base = dirs.get(str(options.get(CONF_MEDIA_DIR) or ""))
    if base is None:
        raise ValueError("media_dir")
    folder = clean_folder(str(options.get(CONF_FOLDER) or ""))
    if folder is None:
        raise ValueError("folder")
    root = Path(base)
    target = root / folder
    # Belt and braces: the cleaned folder can't climb out, but check anyway.
    if root.resolve() not in (target.resolve(), *target.resolve().parents):
        raise ValueError("folder")
    return target


def media_content_id(options: Mapping[str, Any], filename: str | None = None) -> str:
    """The Media Source id of the album folder or of one file in it."""
    folder = clean_folder(str(options.get(CONF_FOLDER) or "")) or ""
    path = f"{folder}/{filename}" if filename else folder
    return f"media-source://media_source/{options.get(CONF_MEDIA_DIR)}/{path}"


def _int_in(value: Any, low: int, high: int) -> int | None:
    try:
        number = int(float(value))
    except TypeError, ValueError:
        return None
    return number if low <= number <= high else None


def validate_options(
    hass: HomeAssistant, raw: Mapping[str, Any], current: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, str]]:
    """Merge ``raw`` into ``current`` and validate.

    Returns the cleaned options and a field -> error-key map. Unknown keys
    are dropped. The interval is 0 (manual) or 15 minutes to a week.
    """
    merged = {**current}
    errors: dict[str, str] = {}

    def take(key: str) -> Any:
        return raw[key] if key in raw else merged.get(key)

    interval = _int_in(take(CONF_INTERVAL), 0, MAX_INTERVAL)
    if interval is None or 0 < interval < MIN_INTERVAL:
        errors[CONF_INTERVAL] = "invalid_interval"
    else:
        merged[CONF_INTERVAL] = interval

    for key in (
        CONF_SYNC_PHOTOS,
        CONF_SYNC_VIDEOS,
        CONF_WRITE_LATEST,
        CONF_WRITE_INDEX,
    ):
        merged[key] = bool(take(key))
    if not merged[CONF_SYNC_PHOTOS] and not merged[CONF_SYNC_VIDEOS]:
        errors[CONF_SYNC_PHOTOS] = "nothing_to_sync"

    fmt = str(take(CONF_PHOTO_FORMAT))
    if fmt not in {f.value for f in PhotoFormat}:
        errors[CONF_PHOTO_FORMAT] = "invalid_choice"
    else:
        merged[CONF_PHOTO_FORMAT] = fmt
    mode = str(take(CONF_LEAVE_MODE))
    if mode not in {m.value for m in LeaveMode}:
        errors[CONF_LEAVE_MODE] = "invalid_choice"
    else:
        merged[CONF_LEAVE_MODE] = mode

    media_dir = str(take(CONF_MEDIA_DIR) or "")
    if media_dir not in hass.config.media_dirs:
        errors[CONF_MEDIA_DIR] = "invalid_media_dir"
    else:
        merged[CONF_MEDIA_DIR] = media_dir
    folder = clean_folder(str(take(CONF_FOLDER) or ""))
    if folder is None:
        errors[CONF_FOLDER] = "invalid_folder"
    else:
        merged[CONF_FOLDER] = folder

    for key, high in (
        (CONF_KEEP_DAYS, 36500),
        (CONF_MAX_FILES, 1_000_000),
        (CONF_MIN_SIZE_KB, 1_000_000),
        (CONF_MIN_LONG_EDGE, 20000),
        (CONF_MIN_FREE_MB, 10_000_000),
    ):
        number = _int_in(take(key), 0, high)
        if number is None:
            errors[key] = "invalid_number"
        else:
            merged[key] = number
    concurrency = _int_in(take(CONF_CONCURRENCY), 1, MAX_CONCURRENCY)
    if concurrency is None:
        errors[CONF_CONCURRENCY] = "invalid_number"
    else:
        merged[CONF_CONCURRENCY] = concurrency
    quality = _int_in(take(CONF_JPEG_QUALITY), 50, 100)
    if quality is None:
        errors[CONF_JPEG_QUALITY] = "invalid_number"
    else:
        merged[CONF_JPEG_QUALITY] = quality

    hosts_raw = take(CONF_EXTRA_HOSTS) or []
    if isinstance(hosts_raw, str):
        hosts_raw = re.split(r"[\s,]+", hosts_raw)
    hosts: list[str] = []
    for item in hosts_raw:
        if not str(item).strip():
            continue
        host = normalize_extra_host(str(item))
        if host is None:
            errors[CONF_EXTRA_HOSTS] = "invalid_host"
            break
        if host not in hosts:
            hosts.append(host)
    else:
        merged[CONF_EXTRA_HOSTS] = hosts

    return merged, errors
