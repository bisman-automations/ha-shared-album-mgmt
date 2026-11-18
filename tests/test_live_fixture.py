"""A real public album, recorded live in November 2026 and sanitized.

``fixtures/live_resolve.json`` and ``fixtures/live_query.json`` keep Apple's
structure and field names exactly; ids, tokens, names, URLs, checksums,
dates, file names and metadata were replaced. What this album showed:

- The partition is ``https://p49-ckdatabasews.icloud.com:443`` (numbered host,
  with an explicit port).
- There is no ``rootRecord``: the title is the share's ``cloudkit.title``.
- Masters carry only ``resOriginalRes`` and ``resJPEGThumbRes`` (no
  ``JPEGMed``), downloads come from ``cvws-h2.icloud-content.com``.
- ``extendedDescEnc`` held ``Signature: <token>`` rather than a caption.
- There is no contributor field on modern albums.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from custom_components.shared_album_mgmt.api import (
    SharedAlbumClient,
    _caption,
    parse_cloudkit_records,
)
from custom_components.shared_album_mgmt.const import PhotoFormat
from custom_components.shared_album_mgmt.hosts import HostKind, is_trusted_host
from custom_components.shared_album_mgmt.links import parse_link

from .fake_apple import FakeResponse

FIXTURES = Path(__file__).parent / "fixtures"
RESOLVE = json.loads((FIXTURES / "live_resolve.json").read_text())
QUERY = json.loads((FIXTURES / "live_query.json").read_text())
LINK = "Https://Photos.iCloud.com/shared/album/REDACTEDALBUMID01"


class RecordedSession:
    """Answers resolve and query with the recorded responses."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def post(self, url: str, **kwargs: Any) -> Any:
        self.urls.append(url)
        body = RESOLVE if url.endswith("/records/resolve") else QUERY
        data = json.dumps(body).encode()
        return _Ctx(FakeResponse(200, data, {"Content-Type": "text/plain"}))


class _Ctx:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    def __await__(self):  # type: ignore[no-untyped-def]
        async def done() -> FakeResponse:
            return self.response

        return done().__await__()

    async def __aenter__(self) -> FakeResponse:
        return self.response

    async def __aexit__(self, *exc: object) -> None:
        return None


def test_mixed_case_link() -> None:
    """Links typed with capitals in the scheme or host still parse."""
    link = parse_link(LINK)
    assert link.album_id == "REDACTEDALBUMID01"
    assert (
        parse_link("HTTPS://PHOTOS.ICLOUD.COM/shared/album/REDACTEDALBUMID01") == link
    )


async def test_recorded_album_lists() -> None:
    """The real response shape lists every photo with its title and dates."""
    session = RecordedSession()
    listing = await SharedAlbumClient(session, parse_link(LINK)).async_list()  # type: ignore[arg-type]
    assert listing.name == "Sample Album"
    assert len(listing.items) == 5
    assert all(not item.is_video for item in listing.items)
    query_host = urlparse(session.urls[1])
    assert query_host.hostname == "p49-ckdatabasews.icloud.com"
    assert query_host.port == 443
    captured = [item.captured_at for item in listing.items]
    assert all(captured)
    assert captured == sorted(captured, reverse=True)
    for item in listing.items:
        assert item.caption == ""  # the Signature token is not a caption
        assert item.contributor == ""
        assert item.stem.startswith("IMG_")
        assert [d.key for d in item.derivatives] == ["Original"]
        original = item.derivatives[0]
        assert (
            original.is_jpeg
            and original.size > 0
            and original.width
            and original.height
        )
        assert "${f}" in original.url
        host = urlparse(original.url).hostname
        assert host == "cvws-h2.icloud-content.com"
        assert is_trusted_host(host, HostKind.DOWNLOAD)
        # Only the original exists, so every Photo format takes it.
        for fmt in PhotoFormat:
            assert item.choose(fmt) is original


def test_recorded_records_without_asset_dates_fall_back() -> None:
    """Masters alone still parse (dates from the master)."""
    masters = [r for r in QUERY["records"] if r["recordType"] == "CPLMaster"]
    items = parse_cloudkit_records(masters)
    assert len(items) == 5
    assert all(item.captured_at for item in items)


def _enc(text: str) -> dict[str, str]:
    import base64

    return {
        "value": base64.b64encode(text.encode()).decode(),
        "type": "ENCRYPTED_BYTES",
    }


def test_caption_rules() -> None:
    """Real captions are kept; machine data in the description is not."""
    assert _caption({"captionEnc": _enc("Beach day")}) == "Beach day"
    assert (
        _caption({"extendedDescEnc": _enc("First snow\nof the year")})
        == "First snow\nof the year"
    )
    assert _caption({"extendedDescEnc": _enc("Signature: " + "A" * 900)}) == ""
    assert _caption({"extendedDescEnc": _enc("x" * 100)}) == ""
    assert _caption({"captionEnc": {"value": "%%%"}}) == ""
    assert _caption({}) == ""


def test_no_personal_data_in_fixtures() -> None:
    """The fixtures hold no owner identity, participants or tokens."""
    text = json.dumps(RESOLVE) + json.dumps(QUERY)
    for needle in (
        "participants",
        "ownerIdentity",
        "emailAddress",
        "givenName",
        "familyName",
        "lookupInfo",
    ):
        assert needle not in text


def test_title_falls_back_to_root_record() -> None:
    """Older responses with a root record still give the album name."""
    _root_name = SharedAlbumClient._root_name

    name = _enc("Older Album")
    assert (
        _root_name({"rootRecord": {"fields": {"albumNameEnc": name}}}) == "Older Album"
    )
    assert (
        _root_name(
            {
                "share": {"fields": {"cloudkit.title": {"value": " "}}},
                "rootRecord": {"fields": {"albumNameEnc": name}},
            }
        )
        == "Older Album"
    )
    assert _root_name(RESOLVE["results"][0]) == "Sample Album"
