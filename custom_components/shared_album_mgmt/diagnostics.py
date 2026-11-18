"""Diagnostics. The album id, link, tokens and file names are redacted."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import SharedAlbumConfigEntry
from .const import CONF_ALBUM_ID, CONF_EXTRA_HOSTS, CONF_URL
from .convert import heic_available

TO_REDACT = {CONF_URL, CONF_ALBUM_ID, "token", "publicAccessAuthToken", "url"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SharedAlbumConfigEntry
) -> dict[str, Any]:
    """What a bug report needs, without the album link or photo names."""
    coordinator = entry.runtime_data
    state = coordinator.store.state
    snap = coordinator.data
    by_type: dict[str, int] = {}
    by_format: dict[str, int] = {}
    for record in state.assets.values():
        by_type[record.media_type] = by_type.get(record.media_type, 0) + 1
        by_format[record.photo_format] = by_format.get(record.photo_format, 0) + 1
    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": {
                **dict(entry.options),
                CONF_EXTRA_HOSTS: list(entry.options.get(CONF_EXTRA_HOSTS) or []),
            },
        },
        "heic_available": heic_available(),
        "syncing": coordinator.syncing,
        "store": {
            "assets": len(state.assets),
            "by_media_type": by_type,
            "by_photo_format": by_format,
            "quarantine": len(state.quarantine),
            "baseline": state.baseline,
            "pending_removal": len(state.pending_removal),
            "remote_count": state.remote_count,
            "last_success": state.last_success,
            "last_attempt": state.last_attempt,
            "last_error": state.last_error,
            "last_error_placeholders": state.last_error_placeholders,
        },
        "snapshot": {
            "status": snap.status if snap else None,
            "item_count": snap.item_count if snap else None,
            "bytes_used": snap.bytes_used if snap else None,
            "last_result": snap.last_result if snap else None,
        },
    }
