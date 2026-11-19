"""One coordinator per album.

The coordinator's data is a :class:`AlbumSnapshot`: status, counts, the
last run and the last error, built from the store. Setup never waits for
Apple: entities start from what was stored, and the first sync runs in the
background. Errors don't make entities unavailable; they show up in the
Last error sensor, the Problem binary sensor, the panel and, where the user
can act, a Repairs issue.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from pathlib import Path
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import SharedAlbumClient, describe_error
from .catalog import async_write_catalog
from .const import (
    CONF_EXTRA_HOSTS,
    CONF_INTERVAL,
    CONF_PHOTO_FORMAT,
    DOMAIN,
    ISSUE_ALBUM_GONE,
    ISSUE_HEIC_UNAVAILABLE,
    ISSUE_LOW_DISK,
    ISSUE_UNTRUSTED_HOST,
    SIGNAL_UPDATED,
    PhotoFormat,
)
from .convert import heic_available
from .exceptions import (
    AlbumNotFoundError,
    AlbumRequiresLoginError,
    LowDiskSpaceError,
    SharedAlbumError,
    UntrustedHostError,
)
from .links import AlbumLink
from .store import AlbumStore
from .sync import AlbumSyncer, SyncResult

_LOGGER = logging.getLogger(__name__)

STATUS_IDLE = "idle"
STATUS_SYNCING = "syncing"
STATUS_ERROR = "error"
PROGRESS_THROTTLE = 0.5  # seconds between progress pushes to the panel


@dataclass(slots=True)
class AlbumSnapshot:
    """What entities and the panel show."""

    status: str = STATUS_IDLE
    item_count: int = 0
    remote_count: int = 0
    bytes_used: int = 0
    quarantine_count: int = 0
    last_sync: datetime | None = None
    last_error: str | None = None
    last_error_placeholders: dict[str, str] = field(default_factory=dict)
    last_result: dict[str, Any] | None = None
    latest_file: str | None = None
    progress: dict[str, Any] | None = None

    @property
    def problem(self) -> bool:
        """An error or download failures on the last run."""
        return self.last_error is not None


class AlbumCoordinator(DataUpdateCoordinator[AlbumSnapshot]):
    """Schedules syncs for one album and publishes its snapshot."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        link: AlbumLink,
        options: dict[str, Any],
        target: Path,
    ) -> None:
        """Set up the client, store and engine for the entry.

        ``target`` is the album folder already confirmed by
        :func:`options.async_resolve_target` (executor I/O done in setup).
        """
        interval = int(options[CONF_INTERVAL])
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=timedelta(minutes=interval) if interval else None,
            always_update=True,
        )
        self.link = link
        self.options = options
        self.store = AlbumStore(hass, entry.entry_id)
        self.client = SharedAlbumClient(
            async_get_clientsession(hass), link, extra_hosts=options[CONF_EXTRA_HOSTS]
        )
        self.target = target
        self.syncer = AlbumSyncer(
            hass, self.client, self.store, self.target, options, entry.title
        )
        self._lock = asyncio.Lock()
        self._progress: dict[str, Any] | None = None
        self._last_push = 0.0
        self._last_result: SyncResult | None = None
        self.latest_changed: datetime | None = None

    async def async_load(self) -> None:
        """Read the store and publish a snapshot without contacting Apple."""
        await self.store.async_load()
        self.async_set_updated_data(self._snapshot())

    @property
    def syncing(self) -> bool:
        """A sync is running."""
        return self._lock.locked()

    def _snapshot(self) -> AlbumSnapshot:
        state = self.store.state
        latest = state.assets.get(state.latest_guid) if state.latest_guid else None
        return AlbumSnapshot(
            status=STATUS_SYNCING
            if self.syncing
            else (STATUS_ERROR if state.last_error else STATUS_IDLE),
            item_count=len(state.assets),
            remote_count=state.remote_count,
            bytes_used=self.syncer.bytes_used(),
            quarantine_count=len(state.quarantine),
            last_sync=dt_util.parse_datetime(state.last_success)
            if state.last_success
            else None,
            last_error=state.last_error,
            last_error_placeholders=dict(state.last_error_placeholders),
            last_result=self._last_result.as_dict() if self._last_result else None,
            latest_file=latest.file if latest else None,
            progress=self._progress,
        )

    @callback
    def async_publish(self) -> None:
        """Push a fresh snapshot to entities and the panel."""
        self.async_set_updated_data(self._snapshot())
        async_dispatcher_send(self.hass, SIGNAL_UPDATED, self.config_entry.entry_id)

    async def _async_update_data(self) -> AlbumSnapshot:
        """Scheduled refresh: run a sync (never raises UpdateFailed)."""
        await self.async_sync()
        return self._snapshot()

    async def async_sync(self, *, verify: bool = False) -> SyncResult | None:
        """Run one sync now. Returns None when one is already running."""
        if self._lock.locked():
            return None
        async with self._lock:
            state = self.store.state
            previous_latest = state.latest_guid
            self._progress = {"done": 0, "total": 0, "current": None}
            self.async_publish()
            result: SyncResult | None = None
            try:
                done = await self.syncer.async_sync(self._on_progress, verify=verify)
            except SharedAlbumError as err:
                key, placeholders = describe_error(err)
                state.last_error = key
                state.last_error_placeholders = placeholders
                _LOGGER.warning("%s: sync failed: %s", self.config_entry.title, err)
                self._raise_issue(err)
                await self.store.async_save()
            except OSError as err:
                state.last_error = "storage_error"
                state.last_error_placeholders = {
                    "error": err.strerror or type(err).__name__
                }
                _LOGGER.warning("%s: folder problem: %s", self.config_entry.title, err)
                await self.store.async_save()
            else:
                result = done
                self._last_result = result
                state.last_success = result.finished_at
                if result.failed:
                    state.last_error = "download_failed"
                    state.last_error_placeholders = {"count": str(result.failed)}
                else:
                    state.last_error = None
                    state.last_error_placeholders = {}
                self._clear_issues()
                self._heic_issue(result)
                await self.store.async_save()
            finally:
                self._progress = None
            if state.latest_guid != previous_latest:
                self.latest_changed = dt_util.utcnow()
        self.async_publish()
        await async_write_catalog(self.hass)
        return result

    @callback
    def _on_progress(self, done: int, total: int, current: str | None) -> None:
        self._progress = {"done": done, "total": total, "current": current}
        now = time.monotonic()
        if done in (0, total) or now - self._last_push >= PROGRESS_THROTTLE:
            self._last_push = now
            self.async_publish()

    # -- repairs ------------------------------------------------------------

    def _issue_id(self, kind: str) -> str:
        return f"{kind}_{self.config_entry.entry_id}"

    def _raise_issue(self, err: SharedAlbumError) -> None:
        title = self.config_entry.title
        if isinstance(err, UntrustedHostError):
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self._issue_id(ISSUE_UNTRUSTED_HOST),
                is_fixable=True,
                is_persistent=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key=ISSUE_UNTRUSTED_HOST,
                translation_placeholders={
                    "album": title,
                    "host": err.host,
                    "kind": err.kind,
                },
                data={"entry_id": self.config_entry.entry_id, "host": err.host},
            )
        elif isinstance(err, LowDiskSpaceError):
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self._issue_id(ISSUE_LOW_DISK),
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_LOW_DISK,
                translation_placeholders={"album": title, **err.placeholders},
            )
        elif isinstance(err, AlbumNotFoundError | AlbumRequiresLoginError):
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self._issue_id(ISSUE_ALBUM_GONE),
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key=ISSUE_ALBUM_GONE,
                translation_placeholders={"album": title},
            )

    def _clear_issues(self) -> None:
        for kind in (ISSUE_UNTRUSTED_HOST, ISSUE_LOW_DISK, ISSUE_ALBUM_GONE):
            ir.async_delete_issue(self.hass, DOMAIN, self._issue_id(kind))

    def _heic_issue(self, result: SyncResult) -> None:
        wants_convert = self.options[CONF_PHOTO_FORMAT] == PhotoFormat.CONVERT.value
        if wants_convert and result.heic_fallback and not heic_available():
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_HEIC_UNAVAILABLE,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_HEIC_UNAVAILABLE,
            )
