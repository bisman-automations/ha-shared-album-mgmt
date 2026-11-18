"""Read a public iCloud shared album.

Two read paths, one result shape (:class:`AlbumListing`):

Modern links (``photos.icloud.com/shared/album/<id>``)
    1. ``POST https://ckdatabasews.icloud.com/database/1/com.apple.photos.cloud/
       production/public/records/resolve`` with the id as a short GUID. The
       answer has an anonymous, short-lived token, the album's CloudKit zone
       and a *database partition* URL (``https://pNN-ckdatabasews...``).
    2. ``POST <partition>/database/1/com.apple.photos.cloud/production/shared/
       records/query`` with that token, paging through
       ``CPLAssetAndMasterByAssetDateWithoutHiddenOrDeleted`` until there is no
       ``continuationMarker``. ``CPLMaster`` records carry the files
       (``res<Name>Res`` fields with a ``downloadURL``); ``CPLAsset`` records
       carry the asset date and point at their master with ``masterRef``.

Legacy links (``www.icloud.com/sharedalbum/#<id>``)
    1. ``POST https://p23-sharedstreams.icloud.com/<id>/sharedstreams/webstream``.
       Apple usually answers 330 with ``X-Apple-MMe-Host`` naming the album's
       partition host; the request is repeated there.
    2. ``POST .../webasseturls`` with the photo GUIDs, which maps each
       derivative checksum to a download location.

Every host Apple names is checked by :mod:`.hosts` before it is called, and
redirects are followed by hand so a redirect can't skip that check. The
anonymous token is used only for the requests of one listing and is never
stored or logged.

This module was written for this integration against Apple's public
shared-album endpoints.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
import logging
import os
import re
from typing import Any
from urllib.parse import quote, unquote, urljoin, urlparse

import aiohttp

from .const import (
    BACKOFF_SECONDS,
    DOWNLOAD_TIMEOUT,
    MAX_ATTEMPTS,
    REQUEST_TIMEOUT,
    USER_AGENT,
    LinkKind,
    PhotoFormat,
)
from .exceptions import (
    AlbumNotFoundError,
    AlbumRequiresLoginError,
    AppleApiError,
    CannotConnectError,
    DownloadError,
    IncompleteListingError,
    SharedAlbumError,
)
from .hosts import HostKind, require_trusted_url
from .links import AlbumLink, redact_id

_LOGGER = logging.getLogger(__name__)

CLOUDKIT_CONTAINER = "com.apple.photos.cloud"
CLOUDKIT_BOOTSTRAP = "https://ckdatabasews.icloud.com"
CLOUDKIT_BOOTSTRAP_CN = "https://ckdatabasews.icloud.com.cn"
SHAREDSTREAMS_BOOTSTRAP = "p23-sharedstreams.icloud.com"
SHAREDSTREAMS_BOOTSTRAP_CN = "p23-sharedstreams.icloud.com.cn"
QUERY_RECORD_TYPE = "CPLAssetAndMasterByAssetDateWithoutHiddenOrDeleted"
QUERY_PAGE = 100
ASSET_URL_BATCH = 50
MAX_PAGES = 2000  # 200,000 records: a safety stop, far beyond Apple's limits
MAX_REDIRECTS = 3

IMAGE = "image"
VIDEO = "video"

_RES_FIELD = re.compile(r"res(?P<name>[A-Za-z]+?)Res")
_VIDEO_TYPES = ("video", "movie", "quicktime", "mpeg", "mp4")
_SAFE_STEM = re.compile(r"[^\w .-]+")


@dataclass(frozen=True, slots=True)
class Derivative:
    """One downloadable rendition of an item."""

    key: str  # Apple's name: "Original", "JPEGMed", "2048", "720p", ...
    url: str
    width: int = 0
    height: int = 0
    size: int = 0
    file_type: str = ""  # UTI or extension, lowercase

    @property
    def pixels(self) -> int:
        """Width times height (0 when Apple didn't say)."""
        return self.width * self.height

    @property
    def long_edge(self) -> int:
        """The longer side in pixels."""
        return max(self.width, self.height)

    @property
    def is_heic(self) -> bool:
        """HEIC or HEIF, which browsers mostly can't show."""
        return "heic" in self.file_type or "heif" in self.file_type

    @property
    def is_jpeg(self) -> bool:
        """A JPEG rendition."""
        return "jpeg" in self.file_type or "jpg" in self.file_type

    @property
    def is_original(self) -> bool:
        """Apple's stored original rather than a rendered copy."""
        return self.key.lower().startswith("original")

    @property
    def extension(self) -> str:
        """File extension, with the dot, that matches the file type."""
        kind = self.file_type
        if self.is_heic:
            return ".heic"
        if self.is_jpeg:
            return ".jpg"
        for token, ext in (
            ("png", ".png"),
            ("gif", ".gif"),
            ("webp", ".webp"),
            ("tiff", ".tiff"),
            ("dng", ".dng"),
            ("quicktime", ".mov"),
            ("mov", ".mov"),
            ("mpeg-4", ".mp4"),
            ("mp4", ".mp4"),
            ("m4v", ".m4v"),
        ):
            if token in kind:
                return ext
        return ""


@dataclass(slots=True)
class RemoteAsset:
    """One photo or video in the album."""

    guid: str
    media_type: str
    stem: str
    captured_at: str | None = None
    contributor: str = ""
    caption: str = ""
    derivatives: list[Derivative] = field(default_factory=list)

    @property
    def is_video(self) -> bool:
        """A video (Live Photo motion parts are not listed as items)."""
        return self.media_type == VIDEO

    def eligible(self, min_long_edge: int, min_bytes: int) -> list[Derivative]:
        """Renditions that pass the album's minimum size filters.

        A rendition with no reported width (or size) is not rejected on that
        measure, because Apple sometimes leaves it out.
        """
        return [
            d
            for d in self.derivatives
            if not (d.long_edge and d.long_edge < min_long_edge)
            and not (d.size and d.size < min_bytes)
        ]

    def choose(
        self,
        photo_format: PhotoFormat,
        *,
        min_long_edge: int = 0,
        min_bytes: int = 0,
        heic_supported: bool = True,
    ) -> Derivative | None:
        """Pick the rendition to save for the album's Photo format.

        - Convert HEIC to JPEG and Keep originals: the largest rendition
          (pixels, then bytes), preferring Apple's original on a tie. When
          HEIC can't be converted, Convert falls back to the largest JPEG.
        - Apple's smaller JPEG: Apple's medium JPEG (``JPEGMed``), otherwise
          the largest JPEG no wider than 2048 px, otherwise the largest
          rendition (public albums often carry only the original; a HEIC one
          is then converted to JPEG). Videos use the medium rendition
          (``VidMed``/``720p``) when there is one.
        """
        candidates = self.eligible(min_long_edge, min_bytes)
        if not candidates:
            return None

        def largest(items: Iterable[Derivative]) -> Derivative | None:
            pool = list(items)
            if not pool:
                return None
            return max(pool, key=lambda d: (d.pixels, d.size, d.is_original))

        if photo_format is PhotoFormat.DASHBOARD:
            if self.is_video:
                medium = [d for d in candidates if d.key.lower() in ("vidmed", "720p")]
                return largest(medium) or largest(candidates)
            exact = [d for d in candidates if d.key.lower() == "jpegmed"]
            if exact:
                return exact[0]
            jpegs = [d for d in candidates if d.is_jpeg]
            small = [d for d in jpegs if d.long_edge and d.long_edge <= 2048]
            return largest(small) or largest(jpegs) or largest(candidates)

        best = largest(candidates)
        if (
            best is not None
            and photo_format is PhotoFormat.CONVERT
            and best.is_heic
            and not heic_supported
        ):
            return largest(d for d in candidates if d.is_jpeg) or best
        return best


@dataclass(slots=True)
class AlbumListing:
    """Everything one complete read of the album returned."""

    name: str
    items: list[RemoteAsset]
    complete: bool = True
    fetched_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )


def _int(value: Any) -> int:
    """Apple sends numbers as numbers or strings; anything else is 0."""
    try:
        return int(float(value))
    except TypeError, ValueError:
        return 0


def _field(fields: dict[str, Any], name: str, default: Any = None) -> Any:
    """Read a CloudKit field's ``value``."""
    item = fields.get(name)
    return item.get("value", default) if isinstance(item, dict) else default


def _iso_from_ms(value: Any) -> str | None:
    """CloudKit timestamps are milliseconds since the epoch."""
    ms = _int(value)
    if ms <= 0:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=UTC).isoformat(timespec="seconds")
    except OverflowError, OSError, ValueError:
        return None


def _iso_from_text(value: Any) -> str | None:
    """Legacy streams send ISO-like strings; keep them only when they parse."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat(timespec="seconds")


def _b64_text(value: Any) -> str:
    """Decode a base64 field such as ``filenameEnc``; empty when it isn't."""
    if not isinstance(value, str) or not value:
        return ""
    try:
        return base64.b64decode(value, validate=True).decode("utf-8").strip()
    except ValueError, UnicodeDecodeError:
        return ""


_TAGGED_BLOB = re.compile(r"[A-Za-z][\w ]{0,40}:\s*\S{64,}")


def _caption(asset_fields: dict[str, Any]) -> str:
    """The photo's caption, or "".

    ``captionEnc`` when present, otherwise ``extendedDescEnc`` (the Photos
    caption/description). Apps sometimes leave machine data there instead,
    such as ``Signature: <long token>`` (seen live), so only text that reads
    like words is used.
    """
    for name in ("captionEnc", "extendedDescEnc"):
        text = _b64_text(_field(asset_fields, name))
        readable = all(c.isprintable() or c in "\n\t" for c in text)
        if not text or not readable or _TAGGED_BLOB.fullmatch(text):
            continue
        if any(len(word) > 64 for word in text.split()):
            continue
        return text[:2000]
    return ""


def safe_stem(name: str, guid: str) -> str:
    """A filesystem-safe file stem from Apple's original filename.

    Path separators and control characters are dropped, so a crafted
    filename can never leave the album folder.
    """
    stem = os.path.splitext(os.path.basename(name.replace("\\", "/")))[0]
    stem = _SAFE_STEM.sub("_", stem).strip(" ._")[:80]
    return stem or f"icloud_{guid[:12]}"


def _cloudkit_derivatives(fields: dict[str, Any], is_video: bool) -> list[Derivative]:
    """Collect every ``res<Name>Res`` rendition of a CPLMaster or CPLAsset."""
    found: list[Derivative] = []
    for name in fields:
        match = _RES_FIELD.fullmatch(name)
        if not match:
            continue
        key = match.group("name")
        lowered = key.lower()
        if "thumb" in lowered or "poster" in lowered or "square" in lowered:
            continue
        if not is_video and "vid" in lowered:
            continue  # the motion part of a Live Photo
        asset = _field(fields, name)
        if not isinstance(asset, dict) or not isinstance(asset.get("downloadURL"), str):
            continue
        if is_video and "vid" not in lowered and not lowered.startswith("original"):
            continue  # still renders of a video
        found.append(
            Derivative(
                key=key,
                url=str(asset["downloadURL"]),
                width=_int(_field(fields, f"res{key}Width")),
                height=_int(_field(fields, f"res{key}Height")),
                size=_int(asset.get("size") or _field(fields, f"res{key}FileSize")),
                file_type=str(_field(fields, f"res{key}FileType", "")).lower(),
            )
        )
    return found


def parse_cloudkit_records(records: list[dict[str, Any]]) -> list[RemoteAsset]:
    """Turn CPLMaster/CPLAsset records into assets, newest first.

    Masters carry files; assets carry the date the photo was taken and may
    carry an edited render. Each asset is joined to its master through
    ``masterRef``. A master with no asset record is still listed.
    """
    masters: dict[str, dict[str, Any]] = {}
    asset_for_master: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for record in records:
        if not isinstance(record, dict) or record.get("deleted"):
            continue
        fields = record.get("fields")
        name = str(record.get("recordName") or "")
        if not isinstance(fields, dict) or not name:
            continue
        if record.get("recordType") == "CPLMaster":
            masters[name] = fields
            if name not in order:
                order.append(name)
        elif record.get("recordType") == "CPLAsset":
            ref = _field(fields, "masterRef")
            master = str(ref.get("recordName") or "") if isinstance(ref, dict) else ""
            if master:
                asset_for_master[master] = fields
                if master not in order:
                    order.append(master)

    items: list[RemoteAsset] = []
    for guid in order:
        fields = masters.get(guid)
        if fields is None:
            continue
        asset_fields = asset_for_master.get(guid, {})
        item_type = str(_field(fields, "itemType", "")).lower()
        is_video = any(token in item_type for token in _VIDEO_TYPES)
        derivatives = _cloudkit_derivatives(fields, is_video)
        # An edited photo's render lives on the asset record.
        derivatives += [
            d
            for d in _cloudkit_derivatives(asset_fields, is_video)
            if d.url not in {x.url for x in derivatives}
        ]
        if not derivatives:
            continue
        filename = _b64_text(_field(fields, "filenameEnc"))
        captured = _iso_from_ms(_field(asset_fields, "assetDate")) or _iso_from_ms(
            _field(fields, "originalCreationDate") or _field(fields, "importDate")
        )
        caption = _caption(asset_fields)
        items.append(
            RemoteAsset(
                guid=guid,
                media_type=VIDEO if is_video else IMAGE,
                stem=safe_stem(filename, guid),
                captured_at=captured,
                caption=caption,
                derivatives=derivatives,
            )
        )
    return items


def parse_webstream(
    stream: dict[str, Any], asset_urls: dict[str, dict[str, Any]]
) -> list[RemoteAsset]:
    """Turn a legacy ``webstream`` answer plus its asset URLs into assets."""
    items: list[RemoteAsset] = []
    for photo in stream.get("photos") or []:
        if not isinstance(photo, dict):
            continue
        guid = str(photo.get("photoGuid") or "")
        derivatives = photo.get("derivatives")
        if not guid or not isinstance(derivatives, dict):
            continue
        is_video = str(photo.get("mediaAssetType", "")).lower() == VIDEO
        found: list[Derivative] = []
        for key, info in derivatives.items():
            lowered = str(key).lower()
            if not isinstance(info, dict) or "poster" in lowered or "thumb" in lowered:
                continue
            location = asset_urls.get(str(info.get("checksum") or ""))
            if not isinstance(location, dict):
                continue
            url = _legacy_url(location)
            if not url:
                continue
            path_name = unquote(urlparse(url).path).rsplit("/", 1)[-1]
            ext = os.path.splitext(path_name)[1].lower().lstrip(".")
            found.append(
                Derivative(
                    key=str(key),
                    url=url,
                    width=_int(info.get("width")),
                    height=_int(info.get("height")),
                    size=_int(info.get("fileSize") or info.get("size")),
                    file_type=ext or ("mp4" if is_video else "jpeg"),
                )
            )
        if not found:
            continue
        date = photo.get("dateCreated") or photo.get("batchDateCreated")
        items.append(
            RemoteAsset(
                guid=guid,
                media_type=VIDEO if is_video else IMAGE,
                stem=_legacy_stem(_iso_from_text(date), guid),
                captured_at=_iso_from_text(date),
                contributor=str(photo.get("contributorFullName") or "").strip(),
                caption=str(photo.get("caption") or "").strip(),
                derivatives=found,
            )
        )
    return items


def _legacy_stem(captured_at: str | None, guid: str) -> str:
    """Legacy streams don't expose filenames: ``icloud_<yyyymmdd>_<guid8>``."""
    day = (captured_at or "")[:10].replace("-", "")
    return f"icloud_{day}_{guid[:8]}" if day else f"icloud_{guid[:12]}"


def _legacy_url(location: dict[str, Any]) -> str:
    """Build a download URL from a ``webasseturls`` item."""
    path = str(location.get("url_path") or "")
    if path.startswith("https://"):
        return path
    host = str(location.get("url_location") or "")
    if not path or not host:
        return ""
    return f"https://{host}/{path.lstrip('/')}"


class SharedAlbumClient:
    """Reads one album through Home Assistant's shared aiohttp session."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        link: AlbumLink,
        *,
        extra_hosts: Iterable[str] = (),
        request_timeout: float = REQUEST_TIMEOUT,
    ) -> None:
        """Store the session, the album, and any extra trusted hosts."""
        self._session = session
        self.link = link
        self.extra_hosts = tuple(extra_hosts)
        self._timeout = aiohttp.ClientTimeout(total=request_timeout)

    # -- low level ---------------------------------------------------------

    async def _post_json(
        self,
        url: str,
        kind: HostKind,
        payload: dict[str, Any],
        *,
        params: dict[str, str] | None = None,
        text_body: bool = False,
        accept: tuple[int, ...] = (200,),
    ) -> tuple[int, dict[str, Any]]:
        """POST with retries; return the status and the JSON object body.

        Connection errors, 429 and 5xx are retried with exponential backoff
        (``Retry-After`` is honoured, capped at 60 s). Redirects are not
        followed: Apple doesn't redirect these calls, and an unexpected one
        must not reach an unchecked host.
        """
        require_trusted_url(url, kind, self.extra_hosts)
        headers = {"User-Agent": USER_AGENT, "Origin": "https://www.icloud.com"}
        if text_body:
            headers["Content-Type"] = "text/plain"
            body: dict[str, Any] = {"data": json.dumps(payload)}
        else:
            body = {"json": payload}
        last: Exception | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                async with self._session.post(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self._timeout,
                    allow_redirects=False,
                    **body,
                ) as resp:
                    if resp.status == 429 or resp.status >= 500:
                        last = AppleApiError(f"HTTP {resp.status} from {kind.value}")
                        await self._sleep_for(attempt, resp.headers.get("Retry-After"))
                        continue
                    if resp.status == 404:
                        raise AlbumNotFoundError("Apple answered 404")
                    if resp.status not in accept:
                        raise AppleApiError(f"HTTP {resp.status} from {kind.value}")
                    try:
                        data = await resp.json(content_type=None)
                    except (ValueError, aiohttp.ContentTypeError) as err:
                        raise AppleApiError("Apple's answer wasn't JSON") from err
                    if not isinstance(data, dict):
                        raise AppleApiError("Apple's answer wasn't a JSON object")
                    return resp.status, data
            except (TimeoutError, aiohttp.ClientError) as err:
                # The exception text can include the URL and its token.
                last = CannotConnectError(type(err).__name__)
                await self._sleep_for(attempt, None)
        assert last is not None
        raise last

    @staticmethod
    async def _sleep_for(attempt: int, retry_after: str | None) -> None:
        """Back off before the next attempt (not after the last one)."""
        if attempt >= MAX_ATTEMPTS - 1:
            return
        delay = BACKOFF_SECONDS * (2**attempt)
        if retry_after and retry_after.isdigit():
            delay = max(delay, min(60.0, float(retry_after)))
        await asyncio.sleep(delay)

    # -- listings ----------------------------------------------------------

    async def async_list(self) -> AlbumListing:
        """Read the whole album. Raises rather than return a partial list."""
        if self.link.kind is LinkKind.MODERN:
            return await self._list_modern()
        return await self._list_legacy()

    async def _list_modern(self) -> AlbumListing:
        album_id = self.link.album_id
        base = CLOUDKIT_BOOTSTRAP_CN if self.link.china else CLOUDKIT_BOOTSTRAP
        common = {
            "remapEnums": "true",
            "getCurrentSyncToken": "true",
            "sharing_url_key": album_id,
        }
        _, resolved = await self._post_json(
            f"{base}/database/1/{CLOUDKIT_CONTAINER}/production/public/records/resolve",
            HostKind.CLOUDKIT,
            {"shortGUIDs": [{"value": album_id}], "shouldFetchRootRecord": True},
            params=common,
            text_body=True,
        )
        results = resolved.get("results")
        if not isinstance(results, list) or len(results) != 1:
            raise AppleApiError("resolve returned no single result")
        result = results[0] if isinstance(results[0], dict) else {}
        if result.get("serverErrorCode"):
            if result.get("requireAppleLogin"):
                raise AlbumRequiresLoginError(str(result.get("serverErrorCode")))
            if result.get("serverErrorCode") in ("NOT_FOUND", "ZONE_NOT_FOUND"):
                raise AlbumNotFoundError(f"resolve {redact_id(album_id)}: not found")
            raise AppleApiError(f"resolve error {result.get('serverErrorCode')}")
        access = result.get("anonymousPublicAccess")
        zone = result.get("zoneID")
        if not isinstance(access, dict) or not isinstance(zone, dict):
            if result.get("requireAppleLogin"):
                raise AlbumRequiresLoginError("album is not public")
            raise AlbumRequiresLoginError("no anonymous access")
        token = str(access.get("token") or "")
        partition = str(access.get("databasePartition") or "").rstrip("/")
        if not token:
            raise AppleApiError("resolve returned no access token")
        # Apple now answers from numbered partition hosts (pNN-ckdatabasews.icloud.com).
        require_trusted_url(partition, HostKind.CLOUDKIT, self.extra_hosts)

        name = self._root_name(result) or ""
        query_url = f"{partition}/database/1/{CLOUDKIT_CONTAINER}/production/shared/records/query"
        params = {**common, "publicAccessAuthToken": token}
        payload: dict[str, Any] = {
            "query": {
                "recordType": QUERY_RECORD_TYPE,
                "filterBy": [
                    {
                        "fieldName": "direction",
                        "comparator": "EQUALS",
                        "fieldValue": {"value": "DESCENDING", "type": "STRING"},
                    }
                ],
            },
            "zoneID": zone,
            "resultsLimit": QUERY_PAGE,
        }
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for _page in range(MAX_PAGES):
            _, page = await self._post_json(
                query_url, HostKind.CLOUDKIT, payload, params=params, text_body=True
            )
            batch = page.get("records")
            if not isinstance(batch, list):
                raise IncompleteListingError("a page had no records list")
            records.extend(r for r in batch if isinstance(r, dict))
            marker = str(page.get("continuationMarker") or "")
            if not marker:
                break
            if marker in seen:
                raise IncompleteListingError("Apple repeated a page marker")
            seen.add(marker)
            payload["continuationMarker"] = marker
        else:
            raise IncompleteListingError("too many pages")
        return AlbumListing(name=name, items=parse_cloudkit_records(records))

    @staticmethod
    def _root_name(result: dict[str, Any]) -> str | None:
        """The album title from the resolve answer.

        Apple puts it in the share record's ``cloudkit.title`` field (seen
        live, November 2026). A ``rootRecord`` with ``albumNameEnc`` is
        still read in case Apple returns one.
        """
        share = result.get("share")
        share_fields = share.get("fields") if isinstance(share, dict) else None
        if isinstance(share_fields, dict):
            title = str(_field(share_fields, "cloudkit.title", "") or "").strip()
            if title:
                return title
        root = result.get("rootRecord")
        fields = root.get("fields") if isinstance(root, dict) else None
        if not isinstance(fields, dict):
            return None
        return _b64_text(_field(fields, "albumNameEnc")) or (
            str(_field(fields, "title", "") or "").strip() or None
        )

    async def _list_legacy(self) -> AlbumListing:
        album_id = self.link.album_id
        host = (
            SHAREDSTREAMS_BOOTSTRAP_CN if self.link.china else SHAREDSTREAMS_BOOTSTRAP
        )
        payload: dict[str, Any] = {"streamCtag": None}
        stream: dict[str, Any] = {}
        for _hop in range(MAX_REDIRECTS + 1):
            base = f"https://{host}/{album_id}/sharedstreams"
            status, stream = await self._post_json(
                f"{base}/webstream",
                HostKind.SHAREDSTREAMS,
                payload,
                accept=(200, 330),
            )
            assigned = str(stream.get("X-Apple-MMe-Host") or "")
            if status == 330 or (assigned and assigned != host):
                if not assigned:
                    raise AppleApiError("Apple moved the album without saying where")
                require_trusted_url(
                    f"https://{assigned}/", HostKind.SHAREDSTREAMS, self.extra_hosts
                )
                host = assigned
                continue
            break
        else:
            raise AppleApiError("too many partition redirects")
        photos = stream.get("photos")
        if not isinstance(photos, list):
            raise IncompleteListingError("webstream had no photos list")
        expected = _int(stream.get("itemsReturned") or len(photos))
        if expected and expected != len(photos):
            raise IncompleteListingError("webstream count mismatch")
        guids = [
            str(p.get("photoGuid"))
            for p in photos
            if isinstance(p, dict) and p.get("photoGuid")
        ]
        asset_urls: dict[str, dict[str, Any]] = {}
        base = f"https://{host}/{album_id}/sharedstreams"
        for start in range(0, len(guids), ASSET_URL_BATCH):
            _, answer = await self._post_json(
                f"{base}/webasseturls",
                HostKind.SHAREDSTREAMS,
                {"photoGuids": guids[start : start + ASSET_URL_BATCH]},
            )
            items = answer.get("items")
            if not isinstance(items, dict):
                raise IncompleteListingError("webasseturls had no items")
            asset_urls.update({k: v for k, v in items.items() if isinstance(v, dict)})
        listing = parse_webstream(stream, asset_urls)
        return AlbumListing(
            name=str(stream.get("streamName") or "").strip(), items=listing
        )

    # -- downloads ---------------------------------------------------------

    @asynccontextmanager
    async def open_download(self, url: str) -> AsyncIterator[aiohttp.ClientResponse]:
        """Open a download, following up to three redirects by hand.

        Each hop must be HTTPS on a trusted content host. The caller reads
        ``response.content`` in chunks.
        """
        current = url
        for _hop in range(MAX_REDIRECTS + 1):
            require_trusted_url(current, HostKind.DOWNLOAD, self.extra_hosts)
            try:
                resp = await self._session.get(
                    current,
                    headers={"User-Agent": USER_AGENT},
                    timeout=aiohttp.ClientTimeout(
                        total=DOWNLOAD_TIMEOUT, sock_read=REQUEST_TIMEOUT
                    ),
                    allow_redirects=False,
                )
            except (TimeoutError, aiohttp.ClientError) as err:
                raise CannotConnectError(type(err).__name__) from err
            if resp.status in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location", "")
                resp.release()
                if not location:
                    raise DownloadError("redirect without a location")
                current = urljoin(current, location)
                continue
            try:
                if resp.status == 429 or resp.status >= 500:
                    raise CannotConnectError(f"HTTP {resp.status}")
                if resp.status != 200:
                    raise DownloadError(f"HTTP {resp.status}")
                yield resp
            finally:
                resp.release()
            return
        raise DownloadError("too many redirects")


def fill_filename(url: str, filename: str) -> str:
    """CloudKit download URLs carry a ``${f}`` placeholder for the filename."""
    return url.replace("${f}", quote(filename))


def describe_error(err: Exception) -> tuple[str, dict[str, str]]:
    """Translation key and placeholders for an error shown to the user."""
    if isinstance(err, SharedAlbumError):
        return err.translation_key, err.placeholders
    return "unknown", {}


__all__ = [
    "AlbumListing",
    "Derivative",
    "RemoteAsset",
    "SharedAlbumClient",
    "describe_error",
    "fill_filename",
    "parse_cloudkit_records",
    "parse_webstream",
    "safe_stem",
]
