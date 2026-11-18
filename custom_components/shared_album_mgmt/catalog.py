"""``albums.json``: one catalog per folder that holds album folders.

The iCloud Shared Album Sync app writes a catalog next to the album folders
so dashboards can discover albums without being edited. This writes the
same document (version 1) for every parent folder used by a loaded album,
e.g. ``/media/shared_albums/albums.json``.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

from .const import (
    CATALOG_FILENAME,
    DOMAIN,
    INDEX_FILENAME,
    LATEST_FILENAME,
    TEMP_SUFFIX,
)
from .options import media_content_id

if TYPE_CHECKING:
    from .coordinator import AlbumCoordinator

_LOGGER = logging.getLogger(__name__)


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}{TEMP_SUFFIX}")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, path)


def _coordinators(hass: HomeAssistant) -> list[AlbumCoordinator]:
    from .coordinator import AlbumCoordinator  # noqa: PLC0415 - avoid a cycle

    return [
        entry.runtime_data
        for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        if isinstance(getattr(entry, "runtime_data", None), AlbumCoordinator)
    ]


def build_catalogs(hass: HomeAssistant) -> dict[Path, dict[str, Any]]:
    """Catalog documents keyed by the folder they are written to."""
    grouped: dict[Path, list[dict[str, Any]]] = {}
    for coordinator in _coordinators(hass):
        snap = coordinator.data
        options = coordinator.options
        status = "error" if snap and snap.last_error else "ok"
        latest = (
            media_content_id(options, LATEST_FILENAME)
            if snap and snap.latest_file
            else None
        )
        grouped.setdefault(coordinator.target.parent, []).append(
            {
                "name": coordinator.config_entry.title,
                "slug": coordinator.target.name,
                "status": status,
                "item_count": snap.item_count if snap else 0,
                "synced_at": snap.last_sync.isoformat()
                if snap and snap.last_sync
                else None,
                "index": media_content_id(options, INDEX_FILENAME),
                "latest": latest,
                "error": snap.last_error if snap else None,
            }
        )
    now = datetime.now(UTC).isoformat(timespec="seconds")
    return {
        root / CATALOG_FILENAME: {
            "version": 1,
            "generated_at": now,
            "albums": sorted(albums, key=lambda a: str(a["name"]).casefold()),
        }
        for root, albums in grouped.items()
    }


async def async_write_catalog(hass: HomeAssistant) -> None:
    """Write every catalog, in the executor. A failed write is only logged."""
    for path, document in build_catalogs(hass).items():
        try:
            await hass.async_add_executor_job(_write, path, document)
        except OSError as err:
            _LOGGER.warning("Couldn't write %s: %s", path, err)
