"""What this integration remembers about each album.

One ``homeassistant.helpers.storage.Store`` per config entry
(``.storage/shared_album_mgmt.<entry_id>``) holding:

``assets``
    Apple GUID -> the file this integration wrote: path relative to the
    album folder, size, SHA-256, the rendition and Photo format it came
    from, capture date, dimensions, caption, contributor, and whether the
    item is still in the album. The SHA-256 is what makes removals safe: a
    file is only moved or deleted when its bytes are still exactly what was
    downloaded, so a file someone edited or replaced is left alone.
``quarantine``
    Files moved to ``.quarantine`` because their photo left the album.
``baseline``
    False until the first complete listing. Nothing is removed before it.
``pending_removal``
    GUIDs of a held mass removal, applied only when the next listing agrees.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_SAVE_DELAY, STORAGE_VERSION


@dataclass(slots=True)
class AssetRecord:
    """A file written for one Apple item."""

    file: str
    size: int
    sha256: str
    media_type: str
    source_key: str
    photo_format: str
    remote_size: int = 0
    captured_at: str | None = None
    width: int = 0
    height: int = 0
    caption: str = ""
    contributor: str = ""
    downloaded_at: str = ""
    in_album: bool = True
    pinned: bool = False  # restored from quarantine: never removed again


@dataclass(slots=True)
class QuarantineRecord:
    """A file moved aside because its photo left the album."""

    guid: str
    file: str  # where it used to be, relative to the album folder
    stored: str  # where it is now, relative to the album folder
    size: int
    sha256: str
    moved_at: str
    media_type: str = "image"
    captured_at: str | None = None
    reason: str = "left_album"


@dataclass(slots=True)
class AlbumState:
    """Everything stored for one album."""

    assets: dict[str, AssetRecord] = field(default_factory=dict)
    quarantine: dict[str, QuarantineRecord] = field(default_factory=dict)
    baseline: bool = False
    pending_removal: list[str] = field(default_factory=list)
    album_name: str = ""
    last_success: str | None = None
    last_attempt: str | None = None
    last_error: str | None = None
    last_error_placeholders: dict[str, str] = field(default_factory=dict)
    remote_count: int = 0
    latest_guid: str | None = None


class AlbumStore:
    """Load and save :class:`AlbumState` for one config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Create the underlying Store."""
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}", private=True
        )
        self.state = AlbumState()

    async def async_load(self) -> AlbumState:
        """Read the file; a missing or damaged file starts fresh."""
        data = await self._store.async_load() or {}
        state = AlbumState()
        for guid, raw in (data.get("assets") or {}).items():
            try:
                state.assets[guid] = AssetRecord(**raw)
            except TypeError:
                continue
        for qid, raw in (data.get("quarantine") or {}).items():
            try:
                state.quarantine[qid] = QuarantineRecord(**raw)
            except TypeError:
                continue
        state.baseline = bool(data.get("baseline"))
        state.pending_removal = list(data.get("pending_removal") or [])
        state.album_name = str(data.get("album_name") or "")
        state.last_success = data.get("last_success")
        state.last_attempt = data.get("last_attempt")
        state.last_error = data.get("last_error")
        state.last_error_placeholders = dict(data.get("last_error_placeholders") or {})
        state.remote_count = int(data.get("remote_count") or 0)
        state.latest_guid = data.get("latest_guid")
        self.state = state
        return state

    def _serialize(self) -> dict[str, Any]:
        state = self.state
        return {
            "assets": {k: asdict(v) for k, v in state.assets.items()},
            "quarantine": {k: asdict(v) for k, v in state.quarantine.items()},
            "baseline": state.baseline,
            "pending_removal": state.pending_removal,
            "album_name": state.album_name,
            "last_success": state.last_success,
            "last_attempt": state.last_attempt,
            "last_error": state.last_error,
            "last_error_placeholders": state.last_error_placeholders,
            "remote_count": state.remote_count,
            "latest_guid": state.latest_guid,
        }

    def async_delay_save(self) -> None:
        """Save a few seconds from now, coalescing bursts of changes."""
        self._store.async_delay_save(self._serialize, STORAGE_SAVE_DELAY)

    async def async_save(self) -> None:
        """Save now (end of a sync, unload)."""
        await self._store.async_save(self._serialize())

    async def async_remove(self) -> None:
        """Delete the file when the album is removed."""
        await self._store.async_remove()
