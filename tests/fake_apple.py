"""A fake of Apple's public shared-album endpoints, for tests.

Stands in for Home Assistant's aiohttp session. It answers the requests
``api.SharedAlbumClient`` makes, for both link styles, with the same shapes
Apple uses (as seen on Apple's live answers). Knobs on :class:`FakeApple` simulate the
failure cases: Apple's numbered partition hosts, an untrusted host, a
paging loop, empty albums, 429/5xx answers and broken downloads.

Everything here is synthetic; no real album ids or photos.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
import io
import json
from typing import Any
from unittest import mock
from urllib.parse import parse_qs, urlparse

from aiohttp import StreamReader
from multidict import CIMultiDict
from PIL import Image

CONTENT_HOST = "cvws.icloud-content.com"


def jpeg_bytes(
    width: int = 64, height: int = 48, color: tuple[int, int, int] = (200, 30, 30)
) -> bytes:
    """A small real JPEG."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, "JPEG", quality=85)
    return buf.getvalue()


def heic_bytes(
    width: int = 64, height: int = 48, color: tuple[int, int, int] = (30, 160, 60)
) -> bytes:
    """A small real HEIC (needs pillow-heif's encoder)."""
    import pillow_heif  # noqa: PLC0415

    buf = io.BytesIO()
    pillow_heif.from_pillow(Image.new("RGB", (width, height), color)).save(
        buf, quality=80
    )
    return buf.getvalue()


@dataclass
class Variant:
    """One rendition of a fake item."""

    data: bytes
    width: int
    height: int
    file_type: str  # UTI such as public.jpeg / public.heic / com.apple.quicktime-movie


@dataclass
class FakeItem:
    """One photo or video."""

    guid: str
    filename: str
    taken_ms: int
    video: bool = False
    variants: dict[str, Variant] = field(default_factory=dict)


@dataclass
class FakeAlbum:
    """One public album."""

    album_id: str
    name: str
    items: list[FakeItem] = field(default_factory=list)
    partition: str = "https://p51-ckdatabasews.icloud.com"
    legacy_host: str = "p42-sharedstreams.icloud.com"
    requires_login: bool = False


class FakeResponse:
    """Enough of aiohttp.ClientResponse for the client."""

    def __init__(
        self,
        status: int = 200,
        body: bytes = b"",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self._body = body
        self.headers = CIMultiDict(headers or {})
        self.released = False

    async def json(self, content_type: str | None = None) -> Any:
        return json.loads(self._body.decode())

    @property
    def content(self) -> StreamReader:
        stream = StreamReader(mock.Mock(_reading_paused=False), limit=2**16)
        stream.feed_data(self._body)
        stream.feed_eof()
        return stream

    def release(self) -> None:
        self.released = True

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.release()


class _Call:
    """Awaitable and async-context-manager, like aiohttp's request helpers."""

    def __init__(self, coro: Any) -> None:
        self._coro = coro
        self._resp: FakeResponse | None = None

    def __await__(self):  # type: ignore[no-untyped-def]
        return self._coro.__await__()

    async def __aenter__(self) -> FakeResponse:
        self._resp = await self._coro
        return self._resp

    async def __aexit__(self, *exc: object) -> None:
        if self._resp:
            self._resp.release()


class FakeApple:
    """The fake session. Register albums, then hand it to the client."""

    def __init__(self) -> None:
        self.albums: dict[str, FakeAlbum] = {}
        self.page_size = 2
        self.calls: list[tuple[str, str]] = []
        self.fail_download_times: dict[str, int] = {}  # guid -> failures left
        self.status_queue: list[int] = []  # statuses to return before normal answers
        self.repeat_marker = False
        self.empty = False
        self.redirect_downloads_to: str | None = None
        self.wrong_size = False
        self.tokens_seen: list[str] = []
        self.items_returned_extra = 0  # legacy: claim more items than sent

    # -- helpers to build albums -------------------------------------------------

    def add(self, album: FakeAlbum) -> FakeAlbum:
        self.albums[album.album_id] = album
        return album

    @staticmethod
    def photo(
        guid: str,
        filename: str,
        taken_ms: int,
        *,
        heic: bool = False,
        color: tuple[int, int, int] = (200, 30, 30),
    ) -> FakeItem:
        big = heic_bytes(96, 72, color) if heic else jpeg_bytes(96, 72, color)
        return FakeItem(
            guid=guid,
            filename=filename,
            taken_ms=taken_ms,
            variants={
                "Original": Variant(
                    big, 4032, 3024, "public.heic" if heic else "public.jpeg"
                ),
                "JPEGMed": Variant(
                    jpeg_bytes(48, 36, color), 2048, 1536, "public.jpeg"
                ),
                "JPEGThumb": Variant(jpeg_bytes(8, 6, color), 256, 192, "public.jpeg"),
            },
        )

    @staticmethod
    def video(guid: str, filename: str, taken_ms: int) -> FakeItem:
        return FakeItem(
            guid=guid,
            filename=filename,
            taken_ms=taken_ms,
            video=True,
            variants={
                "Original": Variant(
                    b"\x00\x00\x00\x18ftypqt  " + b"v" * 400,
                    1920,
                    1080,
                    "com.apple.quicktime-movie",
                ),
                "VidMed": Variant(
                    b"\x00\x00\x00\x18ftypmp42" + b"m" * 200, 1280, 720, "public.mpeg-4"
                ),
                "VidSmall": Variant(
                    b"\x00\x00\x00\x18ftypmp42" + b"s" * 100, 640, 360, "public.mpeg-4"
                ),
                "JPEGThumb": Variant(jpeg_bytes(8, 6), 256, 144, "public.jpeg"),
            },
        )

    # -- session API --------------------------------------------------------------

    def post(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        data: str | None = None,
        json: Any = None,
        **kwargs: Any,
    ) -> _Call:  # noqa: A002
        return _Call(self._post(url, params or {}, data, json))

    def get(self, url: str, **kwargs: Any) -> _Call:
        return _Call(self._get(url))

    # -- routing ------------------------------------------------------------------

    def _json(self, payload: Any, status: int = 200) -> FakeResponse:
        import json as _json  # noqa: PLC0415

        return FakeResponse(
            status, _json.dumps(payload).encode(), {"Content-Type": "application/json"}
        )

    async def _post(
        self, url: str, params: dict[str, str], data: str | None, body: Any
    ) -> FakeResponse:
        import json as _json  # noqa: PLC0415

        self.calls.append(("POST", url))
        if self.status_queue:
            return FakeResponse(self.status_queue.pop(0), b"", {"Retry-After": "0"})
        parsed = urlparse(url)
        payload = _json.loads(data) if data else (body or {})
        if parsed.path.endswith("/public/records/resolve"):
            return self._resolve(payload)
        if parsed.path.endswith("/shared/records/query"):
            self.tokens_seen.append(params.get("publicAccessAuthToken", ""))
            return self._query(parsed.hostname or "", payload, params)
        parts = parsed.path.strip("/").split("/")
        if len(parts) == 3 and parts[1] == "sharedstreams":
            return self._legacy(parsed.hostname or "", parts[0], parts[2], payload)
        return FakeResponse(404)

    def _resolve(self, payload: dict[str, Any]) -> FakeResponse:
        short = payload["shortGUIDs"][0]["value"]
        album = self.albums.get(short)
        if album is None:
            return self._json(
                {
                    "results": [
                        {
                            "shortGUID": {"value": short},
                            "reason": "Cannot resolve shortGUID",
                            "serverErrorCode": "NOT_FOUND",
                            "requireAppleLogin": False,
                        }
                    ]
                }
            )
        if album.requires_login:
            return self._json(
                {
                    "results": [
                        {"shortGUID": {"value": short}, "requireAppleLogin": True}
                    ]
                }
            )
        return self._json(
            {
                "results": [
                    {
                        "shortGUID": {"value": short},
                        "anonymousPublicAccess": {
                            "token": "anon-token-secret",
                            "databasePartition": album.partition,
                        },
                        "zoneID": {
                            "zoneName": "SharedSync-FAKE",
                            "ownerRecordName": "_owner",
                        },
                        # Live albums carry the title on the share record
                        # (there is no rootRecord).
                        "share": {
                            "recordType": "cloudkit.share",
                            "fields": {
                                "cloudkit.title": {
                                    "value": album.name,
                                    "type": "STRING",
                                }
                            },
                        },
                    }
                ]
            }
        )

    def _album_for_zone(self, params: dict[str, str]) -> FakeAlbum:
        return self.albums[params["sharing_url_key"]]

    def _records(self, album: FakeAlbum) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for item in sorted(album.items, key=lambda i: i.taken_ms, reverse=True):
            fields: dict[str, Any] = {
                "filenameEnc": {
                    "value": base64.b64encode(item.filename.encode()).decode()
                },
                "itemType": {
                    "value": "com.apple.quicktime-movie"
                    if item.video
                    else "public.heic"
                },
                "originalCreationDate": {"value": item.taken_ms},
            }
            for key, variant in item.variants.items():
                fields[f"res{key}Res"] = {
                    "value": {
                        "size": len(variant.data),
                        "downloadURL": f"https://{CONTENT_HOST}/B/{item.guid}/{key}/${{f}}?o=sig",
                    }
                }
                fields[f"res{key}Width"] = {"value": variant.width}
                fields[f"res{key}Height"] = {"value": variant.height}
                fields[f"res{key}FileType"] = {"value": variant.file_type}
            records.append(
                {
                    "recordName": f"A-{item.guid}",
                    "recordType": "CPLAsset",
                    "fields": {
                        "masterRef": {"value": {"recordName": item.guid}},
                        "assetDate": {"value": item.taken_ms},
                    },
                }
            )
            records.append(
                {"recordName": item.guid, "recordType": "CPLMaster", "fields": fields}
            )
        return records

    def _query(
        self, host: str, payload: dict[str, Any], params: dict[str, str]
    ) -> FakeResponse:
        album = self._album_for_zone(params)
        records = [] if self.empty else self._records(album)
        start = int(payload.get("continuationMarker") or 0)
        size = self.page_size * 2
        page = records[start : start + size]
        answer: dict[str, Any] = {"records": page}
        if start + size < len(records):
            answer["continuationMarker"] = (
                "0" if self.repeat_marker and start else str(start + size)
            )
        return self._json(answer)

    def _legacy(
        self, host: str, album_id: str, action: str, payload: dict[str, Any]
    ) -> FakeResponse:
        album = self.albums.get(album_id)
        if album is None:
            return FakeResponse(404)
        if action == "webstream":
            if host != album.legacy_host:
                return self._json({"X-Apple-MMe-Host": album.legacy_host}, status=330)
            photos = []
            for item in [] if self.empty else album.items:
                derivatives = {}
                for key, variant in item.variants.items():
                    legacy_key = {
                        "Original": "2048",
                        "JPEGMed": "1024",
                        "JPEGThumb": "342",
                        "VidMed": "720p",
                        "VidSmall": "360p",
                    }.get(key, key)
                    if item.video and key in ("Original", "JPEGThumb"):
                        continue
                    derivatives[legacy_key] = {
                        "checksum": f"{item.guid}-{key}",
                        "fileSize": str(len(variant.data)),
                        "width": str(variant.width),
                        "height": str(variant.height),
                    }
                if item.video:
                    derivatives["PosterFrame"] = {
                        "checksum": f"{item.guid}-JPEGThumb",
                        "fileSize": "10",
                        "width": "256",
                        "height": "144",
                    }
                photos.append(
                    {
                        "photoGuid": item.guid,
                        "derivatives": derivatives,
                        "mediaAssetType": "video" if item.video else "image",
                        "dateCreated": _iso(item.taken_ms),
                        "caption": "",
                        "contributorFullName": "Test Contributor",
                    }
                )
            return self._json(
                {
                    "streamName": album.name,
                    "itemsReturned": str(len(photos) + self.items_returned_extra),
                    "photos": photos,
                }
            )
        if action == "webasseturls":
            items = {}
            for guid in payload["photoGuids"]:
                item = next(i for i in album.items if i.guid == guid)
                for key, variant in item.variants.items():
                    ext = (
                        "mp4"
                        if "mpeg" in variant.file_type
                        else ("heic" if "heic" in variant.file_type else "jpg")
                    )
                    items[f"{guid}-{key}"] = {
                        "url_location": CONTENT_HOST,
                        "url_path": f"/S/{guid}/{key}/IMG_{guid}.{ext}?o=sig",
                    }
            return self._json(
                {
                    "items": items,
                    "locations": {
                        CONTENT_HOST: {"scheme": "https", "hosts": [CONTENT_HOST]}
                    },
                }
            )
        return FakeResponse(404)

    async def _get(self, url: str) -> FakeResponse:
        self.calls.append(("GET", url))
        parsed = urlparse(url)
        if self.redirect_downloads_to and parsed.hostname == CONTENT_HOST:
            return FakeResponse(
                302,
                b"",
                {"Location": f"https://{self.redirect_downloads_to}{parsed.path}"},
            )
        parts = parsed.path.strip("/").split("/")
        if parsed.hostname != CONTENT_HOST or len(parts) < 3:
            return FakeResponse(404)
        guid, key = parts[1], parts[2]
        left = self.fail_download_times.get(guid, 0)
        if left:
            self.fail_download_times[guid] = left - 1
            return FakeResponse(503)
        for album in self.albums.values():
            for item in album.items:
                if item.guid == guid and key in item.variants:
                    data = item.variants[key].data
                    if self.wrong_size:
                        data = data[:-1]
                    return FakeResponse(200, data)
        return FakeResponse(404)


def _iso(ms: int) -> str:
    from datetime import UTC, datetime  # noqa: PLC0415

    return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def query_params(url: str) -> dict[str, list[str]]:
    """Parse a URL's query (test helper)."""
    return parse_qs(urlparse(url).query)
