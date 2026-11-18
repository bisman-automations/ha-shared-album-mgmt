"""The sync engine: make an album folder match the album.

One :class:`AlbumSyncer` run:

1. Read the whole album (``api.SharedAlbumClient.async_list``). A partial
   listing raises before anything on disk changes.
2. Decide what should be on disk: the Photos/Videos toggles, the rendition
   for the Photo format, the minimum size filters, then Keep days and Max
   files (newest first).
3. Check free space for what is about to be downloaded.
4. Download what is new or changed, a few at a time: stream to a hidden
   ``.<name>.partial`` file in the album folder, hash it while writing,
   check the size, convert HEIC to JPEG when asked, then rename into place
   (an atomic replace on the same filesystem). Transient failures are
   retried with backoff.
5. Handle items that left the album with the album's "When a photo leaves
   the album" choice. Safety rules, in order:
   - nothing is removed until a first complete listing has been recorded
     (the baseline);
   - an empty listing never removes anything (Apple briefly returns empty
     albums during maintenance, and a listing that stopped part way already
     raised in step 1);
   - when more than half of the tracked items (and at least ten) vanish at
     once, the removal waits until the next listing confirms the same set;
   - only files whose size and SHA-256 still match what was downloaded are
     moved or deleted; anything edited or replaced is kept and forgotten.
6. Remove tracked files that the album's own settings no longer want
   (Videos off, Keep days, Max files). Those photos are still in the album,
   so this deletes the local copy rather than quarantining it.
7. Write ``index.json`` and ``latest.jpg`` (the same shapes the iCloud
   Shared Album Sync app writes, so existing dashboards keep working).

Blocking filesystem work runs in the executor; nothing here blocks the event
loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
from typing import Any

from homeassistant.core import HomeAssistant

from .api import AlbumListing, Derivative, RemoteAsset, SharedAlbumClient, fill_filename
from .const import (
    BACKOFF_SECONDS,
    CONF_CONCURRENCY,
    CONF_JPEG_QUALITY,
    CONF_KEEP_DAYS,
    CONF_LEAVE_MODE,
    CONF_MAX_FILES,
    CONF_MIN_FREE_MB,
    CONF_MIN_LONG_EDGE,
    CONF_MIN_SIZE_KB,
    CONF_PHOTO_FORMAT,
    CONF_SYNC_PHOTOS,
    CONF_SYNC_VIDEOS,
    CONF_WRITE_INDEX,
    CONF_WRITE_LATEST,
    DOWNLOAD_CHUNK,
    INDEX_FILENAME,
    LATEST_FILENAME,
    MASS_REMOVAL_MIN,
    MASS_REMOVAL_RATIO,
    MAX_ATTEMPTS,
    QUARANTINE_DIR,
    RESERVED_NAMES,
    TEMP_SUFFIX,
    LeaveMode,
    PhotoFormat,
)
from .convert import convert_heic_to_jpeg, heic_available
from .exceptions import (
    CannotConnectError,
    DownloadError,
    LowDiskSpaceError,
    SharedAlbumError,
)
from .options import media_content_id
from .store import AlbumStore, AssetRecord, QuarantineRecord

_LOGGER = logging.getLogger(__name__)

# Bytes assumed for an item whose size Apple didn't report.
UNKNOWN_SIZE_GUESS = 10 * 1024 * 1024
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")

ProgressCallback = Callable[[int, int, str | None], None]


def utcnow_iso() -> str:
    """Now, in UTC, to the second."""
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(slots=True)
class Planned:
    """One item the run will download."""

    asset: RemoteAsset
    derivative: Derivative
    filename: str
    convert: bool
    replaces: AssetRecord | None = None


@dataclass(slots=True)
class SyncResult:
    """What one run did. Shown in the panel and in diagnostics."""

    started_at: str = field(default_factory=utcnow_iso)
    finished_at: str | None = None
    remote_count: int = 0
    wanted: int = 0
    downloaded: int = 0
    converted: int = 0
    unchanged: int = 0
    skipped: int = 0
    failed: int = 0
    removed: int = 0
    quarantined: int = 0
    kept: int = 0
    pruned: int = 0
    bytes_downloaded: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    heic_fallback: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Plain dict for JSON."""
        return {name: getattr(self, name) for name in self.__slots__}  # type: ignore[attr-defined]


# --- blocking helpers (executor only) --------------------------------------


def _fs_prepare(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    # Leftovers from an interrupted run.
    for leftover in target.glob(f".*{TEMP_SUFFIX}"):
        leftover.unlink(missing_ok=True)


def _fs_free_bytes(target: Path) -> int:
    return shutil.disk_usage(target).free


def _fs_size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None


def _fs_sha256(path: Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(DOWNLOAD_CHUNK), b""):
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()


def _fs_unchanged(path: Path, size: int, sha256: str) -> bool:
    """True when the file still has exactly the bytes this integration wrote."""
    return _fs_size(path) == size and _fs_sha256(path) == sha256


def _fs_unique(folder: Path, filename: str, taken: set[str]) -> str:
    """A name not used on disk or by another item in this run."""
    stem, ext = os.path.splitext(filename)
    candidate = filename
    counter = 1
    while candidate.lower() in taken or (folder / candidate).exists():
        counter += 1
        candidate = f"{stem}_{counter}{ext}"
    return candidate


def _fs_move(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, target)


def _fs_write_json(path: Path, data: Any) -> None:
    temp = path.with_name(f".{path.name}{TEMP_SUFFIX}")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, path)


def _fs_copy(source: Path, target: Path) -> None:
    temp = target.with_name(f".{target.name}{TEMP_SUFFIX}")
    shutil.copyfile(source, temp)
    os.replace(temp, target)


class _Writer:
    """Write a download to its temp file and hash it, chunk by chunk."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.digest = hashlib.sha256()
        self.size = 0
        self._handle = path.open("wb")

    def write(self, chunk: bytes) -> None:
        self._handle.write(chunk)
        self.digest.update(chunk)
        self.size += len(chunk)

    def close(self) -> None:
        self._handle.close()


# --- the engine --------------------------------------------------------------


class AlbumSyncer:
    """Runs syncs and folder maintenance for one album."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: SharedAlbumClient,
        store: AlbumStore,
        target: Path,
        options: dict[str, Any],
        title: str,
    ) -> None:
        """Bind the album's client, store, folder and options."""
        self.hass = hass
        self.client = client
        self.store = store
        self.target = target
        self.options = options
        self.title = title

    # -- helpers --------------------------------------------------------------

    async def _run(self, func: Callable[..., Any], *args: Any) -> Any:
        return await self.hass.async_add_executor_job(func, *args)

    @property
    def _format(self) -> PhotoFormat:
        return PhotoFormat(self.options[CONF_PHOTO_FORMAT])

    @property
    def _leave_mode(self) -> LeaveMode:
        return LeaveMode(self.options[CONF_LEAVE_MODE])

    def _wanted(
        self, listing: AlbumListing, result: SyncResult
    ) -> list[tuple[RemoteAsset, Derivative]]:
        """Items the settings want on disk, newest first, with their rendition."""
        photos = self.options[CONF_SYNC_PHOTOS]
        videos = self.options[CONF_SYNC_VIDEOS]
        min_bytes = int(self.options[CONF_MIN_SIZE_KB]) * 1024
        min_edge = int(self.options[CONF_MIN_LONG_EDGE])
        heic_ok = self._format is not PhotoFormat.CONVERT or heic_available()
        chosen: list[tuple[RemoteAsset, Derivative]] = []
        for asset in listing.items:
            if (asset.is_video and not videos) or (not asset.is_video and not photos):
                continue
            derivative = asset.choose(
                self._format,
                min_long_edge=min_edge,
                min_bytes=min_bytes,
                heic_supported=heic_ok,
            )
            if derivative is None:
                result.skipped += 1
                continue
            if not heic_ok and derivative.is_heic:
                result.heic_fallback = True
            elif (
                not heic_ok
                and not asset.is_video
                and any(d.is_heic for d in asset.derivatives)
            ):
                result.heic_fallback = True
            chosen.append((asset, derivative))
        chosen.sort(key=lambda pair: pair[0].captured_at or "", reverse=True)
        keep_days = int(self.options[CONF_KEEP_DAYS])
        if keep_days:
            cutoff = (datetime.now(UTC) - timedelta(days=keep_days)).isoformat()
            chosen = [p for p in chosen if (p[0].captured_at or "9999") >= cutoff]
        max_files = int(self.options[CONF_MAX_FILES])
        if max_files:
            chosen = chosen[:max_files]
        return chosen

    def _filename_for(
        self, asset: RemoteAsset, derivative: Derivative
    ) -> tuple[str, bool]:
        """Final filename and whether HEIC will be converted."""
        # Dashboard size converts too: when Apple only has a HEIC original,
        # the dashboard still gets a JPEG.
        convert = (
            self._format in (PhotoFormat.CONVERT, PhotoFormat.DASHBOARD)
            and not asset.is_video
            and derivative.is_heic
            and heic_available()
        )
        ext = (
            ".jpg"
            if convert
            else (derivative.extension or (".mp4" if asset.is_video else ".jpg"))
        )
        return f"{asset.stem}{ext}", convert

    # -- a full run -----------------------------------------------------------

    async def async_sync(
        self, progress: ProgressCallback | None = None, *, verify: bool = False
    ) -> SyncResult:
        """List the album and bring the folder in line. See the module doc."""
        result = SyncResult()
        state = self.store.state
        state.last_attempt = result.started_at
        await self._run(_fs_prepare, self.target)

        listing = await self.client.async_list()
        result.remote_count = len(listing.items)
        if listing.name:
            state.album_name = listing.name

        wanted = self._wanted(listing, result)
        result.wanted = len(wanted)
        plan = await self._plan(wanted, result, verify=verify)

        needed = sum(p.derivative.size or UNKNOWN_SIZE_GUESS for p in plan)
        if plan:
            free = await self._run(_fs_free_bytes, self.target)
            reserve = int(self.options[CONF_MIN_FREE_MB]) * 1024 * 1024
            if free - needed < reserve:
                raise LowDiskSpaceError(free // 1048576, (needed + reserve) // 1048576)

        await self._download_all(plan, result, progress)

        listed = {asset.guid for asset in listing.items}
        await self._handle_departures(listed, result)
        await self._prune_unwanted({a.guid for a, _ in wanted}, listed, result)

        state.remote_count = result.remote_count
        # The listing was complete (a partial one raised above), so later
        # runs may treat a missing item as having left the album.
        state.baseline = True
        await self.async_write_outputs()
        result.finished_at = utcnow_iso()
        if result.failed:
            result.errors.append("download_failed")
        await self.store.async_save()
        return result

    async def _plan(
        self,
        wanted: list[tuple[RemoteAsset, Derivative]],
        result: SyncResult,
        *,
        verify: bool,
    ) -> list[Planned]:
        """Work out which items need downloading."""
        assets = self.store.state.assets
        taken = {r.file.lower() for r in assets.values()}
        plan: list[Planned] = []
        for asset, derivative in wanted:
            filename, convert = self._filename_for(asset, derivative)
            record = assets.get(asset.guid)
            if record is not None:
                record.in_album = True
                same_source = (
                    record.source_key == derivative.key
                    and record.photo_format == self._format.value
                    and (not derivative.size or record.remote_size == derivative.size)
                )
                path = self.target / record.file
                if same_source:
                    if verify:
                        intact = await self._run(
                            _fs_unchanged, path, record.size, record.sha256
                        )
                    else:
                        intact = await self._run(_fs_size, path) == record.size
                    if intact:
                        result.unchanged += 1
                        continue
                # Re-download into the same name when the extension still fits.
                if (
                    os.path.splitext(record.file)[1].lower()
                    == os.path.splitext(filename)[1].lower()
                ):
                    filename = record.file
                    taken.discard(record.file.lower())
            if record is None or filename != record.file:
                filename = await self._run(_fs_unique, self.target, filename, taken)
            taken.add(filename.lower())
            plan.append(Planned(asset, derivative, filename, convert, record))
        return plan

    async def _download_all(
        self, plan: list[Planned], result: SyncResult, progress: ProgressCallback | None
    ) -> None:
        """Download the plan with a concurrency cap; failures don't stop others."""
        total = len(plan)
        done = 0
        semaphore = asyncio.Semaphore(int(self.options[CONF_CONCURRENCY]))
        if progress:
            progress(0, total, None)

        async def one(item: Planned) -> None:
            nonlocal done
            async with semaphore:
                try:
                    await self._download_with_retry(item, result)
                except SharedAlbumError as err:
                    result.failed += 1
                    _LOGGER.warning(
                        "%s: couldn't download %s: %s", self.title, item.filename, err
                    )
                except OSError as err:
                    result.failed += 1
                    _LOGGER.warning(
                        "%s: couldn't save %s: %s", self.title, item.filename, err
                    )
                finally:
                    done += 1
                    if progress:
                        progress(done, total, item.filename)
                    self.store.async_delay_save()

        await asyncio.gather(*(one(item) for item in plan))

    async def _download_with_retry(self, item: Planned, result: SyncResult) -> None:
        last: SharedAlbumError | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                await self._download(item, result)
                return
            except (CannotConnectError, DownloadError) as err:
                last = err
                if attempt < MAX_ATTEMPTS - 1:
                    await asyncio.sleep(BACKOFF_SECONDS * (2**attempt))
        assert last is not None
        raise last

    async def _download(self, item: Planned, result: SyncResult) -> None:
        """Download one item to a temp file, convert if needed, rename into place."""
        final = self.target / item.filename
        temp = self.target / f".{item.filename}{TEMP_SUFFIX}"
        url = fill_filename(
            item.derivative.url, f"{item.asset.stem}{item.derivative.extension}"
        )
        writer: _Writer = await self._run(_Writer, temp)
        try:
            async with self.client.open_download(url) as response:
                buffer = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    buffer += chunk
                    if len(buffer) >= DOWNLOAD_CHUNK:
                        await self._run(writer.write, bytes(buffer))
                        buffer.clear()
                if buffer:
                    await self._run(writer.write, bytes(buffer))
        except BaseException:
            await self._run(writer.close)
            await self._run(lambda: temp.unlink(missing_ok=True))
            raise
        await self._run(writer.close)
        expected = item.derivative.size
        if expected and writer.size != expected:
            await self._run(lambda: temp.unlink(missing_ok=True))
            raise DownloadError(f"size {writer.size} != {expected}")
        if writer.size == 0:
            await self._run(lambda: temp.unlink(missing_ok=True))
            raise DownloadError("empty file")

        size = writer.size
        sha = writer.digest.hexdigest()
        if item.convert:
            jpeg_temp = self.target / f".{item.filename}.jpg{TEMP_SUFFIX}"
            try:
                await self._run(
                    convert_heic_to_jpeg,
                    temp,
                    jpeg_temp,
                    int(self.options[CONF_JPEG_QUALITY]),
                )
            except Exception as err:
                await self._run(lambda: jpeg_temp.unlink(missing_ok=True))
                await self._run(lambda: temp.unlink(missing_ok=True))
                raise DownloadError(
                    f"HEIC conversion failed: {type(err).__name__}"
                ) from err
            await self._run(lambda: temp.unlink(missing_ok=True))
            temp = jpeg_temp
            size = await self._run(_fs_size, temp) or 0
            sha = await self._run(_fs_sha256, temp) or ""
            result.converted += 1

        await self._run(_fs_move, temp, final)
        old = item.replaces
        if old is not None and old.file != item.filename:
            old_path = self.target / old.file
            if await self._run(_fs_unchanged, old_path, old.size, old.sha256):
                await self._run(lambda: old_path.unlink(missing_ok=True))
        self.store.state.assets[item.asset.guid] = AssetRecord(
            file=item.filename,
            size=size,
            sha256=sha,
            media_type=item.asset.media_type,
            source_key=item.derivative.key,
            photo_format=self._format.value,
            remote_size=item.derivative.size,
            captured_at=item.asset.captured_at,
            width=item.derivative.width,
            height=item.derivative.height,
            caption=item.asset.caption,
            contributor=item.asset.contributor,
            downloaded_at=utcnow_iso(),
            in_album=True,
            pinned=old.pinned if old else False,
        )
        result.downloaded += 1
        result.bytes_downloaded += writer.size

    async def _handle_departures(self, listed: set[str], result: SyncResult) -> None:
        """Apply "When a photo leaves the album" with the safety rules."""
        state = self.store.state
        tracked = {g: r for g, r in state.assets.items() if r.in_album and not r.pinned}
        gone = sorted(g for g in tracked if g not in listed)
        if not gone:
            state.pending_removal = []
            return
        if not state.baseline:
            result.warnings.append("baseline_pending")
            return
        if not listed:
            result.warnings.append("empty_listing")
            return
        if (
            len(gone) >= MASS_REMOVAL_MIN
            and len(gone) / max(1, len(tracked)) > MASS_REMOVAL_RATIO
        ):
            if state.pending_removal != gone:
                state.pending_removal = gone
                result.warnings.append("mass_removal_held")
                return
        state.pending_removal = []
        mode = self._leave_mode
        for guid in gone:
            record = state.assets[guid]
            if mode is LeaveMode.KEEP:
                record.in_album = False
                result.kept += 1
                continue
            path = self.target / record.file
            if not await self._run(_fs_unchanged, path, record.size, record.sha256):
                # Edited, replaced or already gone: leave it and forget it.
                del state.assets[guid]
                continue
            if mode is LeaveMode.DELETE:
                await self._run(lambda p=path: p.unlink(missing_ok=True))
                del state.assets[guid]
                result.removed += 1
                continue
            await self._quarantine(guid, record)
            result.quarantined += 1

    async def _quarantine(
        self, guid: str, record: AssetRecord, reason: str = "left_album"
    ) -> None:
        state = self.store.state
        folder = self.target / QUARANTINE_DIR
        stored_name = await self._run(
            _fs_unique,
            folder,
            os.path.basename(record.file),
            {Path(q.stored).name.lower() for q in state.quarantine.values()},
        )
        await self._run(_fs_move, self.target / record.file, folder / stored_name)
        moved_at = utcnow_iso()
        qid = hashlib.sha1(
            f"{guid}{moved_at}".encode(), usedforsecurity=False
        ).hexdigest()[:16]
        state.quarantine[qid] = QuarantineRecord(
            guid=guid,
            file=record.file,
            stored=f"{QUARANTINE_DIR}/{stored_name}",
            size=record.size,
            sha256=record.sha256,
            moved_at=moved_at,
            media_type=record.media_type,
            captured_at=record.captured_at,
            reason=reason,
        )
        del state.assets[guid]

    async def _prune_unwanted(
        self, wanted: set[str], listed: set[str], result: SyncResult
    ) -> None:
        """Delete local copies the album's settings no longer want.

        Only items still in the album (so nothing is lost) and only files
        that are byte-for-byte what was downloaded. Items the run failed to
        download are not touched (they are still wanted).
        """
        state = self.store.state
        for guid in [g for g, r in state.assets.items() if r.in_album and not r.pinned]:
            if guid in wanted or guid not in listed:
                continue
            record = state.assets[guid]
            path = self.target / record.file
            if await self._run(_fs_unchanged, path, record.size, record.sha256):
                await self._run(lambda p=path: p.unlink(missing_ok=True))
                result.pruned += 1
            del state.assets[guid]

    # -- outputs ----------------------------------------------------------------

    async def async_write_outputs(self) -> None:
        """Write index.json and latest.jpg from the store (no network)."""
        state = self.store.state
        items = sorted(
            state.assets.items(), key=lambda kv: kv[1].captured_at or "", reverse=True
        )
        latest = next(
            (
                (guid, r)
                for guid, r in items
                if r.media_type == "image" and r.file.lower().endswith(IMAGE_EXTS)
            ),
            None,
        )
        state.latest_guid = latest[0] if latest else None
        if self.options[CONF_WRITE_LATEST] and latest:
            await self._run(
                _fs_copy, self.target / latest[1].file, self.target / LATEST_FILENAME
            )
        if self.options[CONF_WRITE_INDEX]:
            await self._run(
                _fs_write_json, self.target / INDEX_FILENAME, self.index_document()
            )

    def index_document(self) -> dict[str, Any]:
        """``index.json``: version 2, as written by iCloud Shared Album Sync.

        Extra keys (``media_content_id``, ``in_album``, ``sha256``) are
        additions; readers of the original format ignore them.
        """
        state = self.store.state
        items = []
        for guid, record in sorted(
            state.assets.items(), key=lambda kv: kv[1].captured_at or "", reverse=True
        ):
            items.append(
                {
                    "guid": guid,
                    "filename": record.file,
                    "path": None,
                    "media_content_id": media_content_id(self.options, record.file),
                    "media_type": record.media_type,
                    "captured_at": record.captured_at,
                    "width": record.width,
                    "height": record.height,
                    "expected_size": record.remote_size,
                    "file_size": record.size,
                    "caption": record.caption,
                    "contributor": record.contributor,
                    "in_album": record.in_album,
                    "sha256": record.sha256,
                }
            )
        return {
            "version": 2,
            "album": {"name": state.album_name or self.title, "slug": self.target.name},
            "generated_at": utcnow_iso(),
            "items": items,
        }

    # -- maintenance --------------------------------------------------------------

    async def async_rebuild_index(self) -> int:
        """Forget records whose file is gone, then rewrite index and latest."""
        state = self.store.state
        missing = [
            guid
            for guid, record in state.assets.items()
            if await self._run(_fs_size, self.target / record.file) is None
        ]
        for guid in missing:
            del state.assets[guid]
        for qid in [
            q
            for q, r in state.quarantine.items()
            if await self._run(_fs_size, self.target / r.stored) is None
        ]:
            del state.quarantine[qid]
        await self._run(_fs_prepare, self.target)
        await self.async_write_outputs()
        await self.store.async_save()
        return len(missing)

    async def async_restore(self, qid: str) -> str:
        """Move a quarantined file back and keep it for good (pinned)."""
        state = self.store.state
        record = state.quarantine.pop(qid)
        taken = {r.file.lower() for r in state.assets.values()}
        name = await self._run(_fs_unique, self.target, record.file, taken)
        await self._run(_fs_move, self.target / record.stored, self.target / name)
        state.assets[record.guid] = AssetRecord(
            file=name,
            size=record.size,
            sha256=record.sha256,
            media_type=record.media_type,
            source_key="restored",
            photo_format="restored",
            captured_at=record.captured_at,
            downloaded_at=utcnow_iso(),
            in_album=False,
            pinned=True,
        )
        await self.async_write_outputs()
        await self.store.async_save()
        return name

    async def async_delete_quarantined(self, qids: list[str]) -> int:
        """Delete quarantined files for good."""
        state = self.store.state
        count = 0
        for qid in qids:
            record = state.quarantine.pop(qid, None)
            if record is None:
                continue
            path = self.target / record.stored
            await self._run(lambda p=path: p.unlink(missing_ok=True))
            count += 1
        await self.store.async_save()
        return count

    def quarantine_older_than(self, days: int) -> list[str]:
        """Quarantine ids moved more than ``days`` days ago (0: all)."""
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat(
            timespec="seconds"
        )
        return [
            qid
            for qid, record in self.store.state.quarantine.items()
            if days == 0 or record.moved_at <= cutoff
        ]

    def bytes_used(self) -> int:
        """Bytes of the files this integration keeps (not counting quarantine)."""
        return sum(r.size for r in self.store.state.assets.values())

    def is_reserved(self, name: str) -> bool:
        """Names the engine owns in the album folder."""
        return name in RESERVED_NAMES or name.startswith(".")
