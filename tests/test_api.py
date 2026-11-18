"""Reading albums through both link styles, against the fake Apple."""

from __future__ import annotations

import pytest

from custom_components.shared_album_mgmt.api import (
    Derivative,
    RemoteAsset,
    SharedAlbumClient,
    parse_cloudkit_records,
    safe_stem,
)
from custom_components.shared_album_mgmt.const import PhotoFormat
from custom_components.shared_album_mgmt.exceptions import (
    AlbumNotFoundError,
    AlbumRequiresLoginError,
    AppleApiError,
    CannotConnectError,
    DownloadError,
    IncompleteListingError,
    UntrustedHostError,
)
from custom_components.shared_album_mgmt.links import parse_link

from .conftest import LEGACY_URL, MODERN_URL
from .fake_apple import FakeAlbum, FakeApple


def client(
    apple: FakeApple, url: str = MODERN_URL, extra: tuple[str, ...] = ()
) -> SharedAlbumClient:
    return SharedAlbumClient(apple, parse_link(url), extra_hosts=extra)  # type: ignore[arg-type]


async def test_modern_listing_pages_and_names(apple: FakeApple) -> None:
    """Every page is read; masters and assets are joined; newest first."""
    apple.page_size = 1
    listing = await client(apple).async_list()
    assert listing.name == "Family Photos"
    assert [i.guid for i in listing.items] == ["G1", "G2", "G3"]
    first = listing.items[0]
    assert first.stem == "IMG_0001"
    assert first.media_type == "image"
    assert first.captured_at and first.captured_at.startswith("2026-")
    assert {d.key for d in first.derivatives} == {"Original", "JPEGMed"}  # no thumbs
    video = listing.items[2]
    assert video.is_video
    assert {d.key for d in video.derivatives} == {"Original", "VidMed", "VidSmall"}
    query_calls = [c for c in apple.calls if c[1].endswith("/records/query")]
    assert len(query_calls) == 3
    # The numbered partition host from resolve was used.
    assert all(
        c[1].startswith("https://p51-ckdatabasews.icloud.com/") for c in query_calls
    )
    assert apple.tokens_seen == ["anon-token-secret"] * 3


async def test_legacy_listing_follows_partition_redirect(apple: FakeApple) -> None:
    """The 330 answer names the album's host; the request is repeated there."""
    listing = await client(apple, LEGACY_URL).async_list()
    assert listing.name == "Old Album"
    hosts = [c[1].split("/")[2] for c in apple.calls]
    assert hosts[:2] == ["p23-sharedstreams.icloud.com", "p42-sharedstreams.icloud.com"]
    photo, video = listing.items
    assert photo.contributor == "Test Contributor"
    assert photo.stem.startswith("icloud_2026")
    # The 342 px rendition is listed; size filters and the Photo format decide.
    assert {d.key for d in photo.derivatives} == {"2048", "1024", "342"}
    assert {d.key for d in video.derivatives} == {"720p", "360p"}  # no poster frame


async def test_untrusted_partition_host_is_refused(apple: FakeApple) -> None:
    """A partition outside the allow-list stops the read and names the host."""
    apple.albums["B0zGWZuqDGuWcdR"].partition = "https://p51-ckdatabasews.evil.example"
    with pytest.raises(UntrustedHostError) as err:
        await client(apple).async_list()
    assert err.value.host == "p51-ckdatabasews.evil.example"
    # The extra trusted hosts option lets it through.
    listing = await client(apple, extra=("p51-ckdatabasews.evil.example",)).async_list()
    assert len(listing.items) == 3


async def test_untrusted_legacy_host_is_refused(apple: FakeApple) -> None:
    """The legacy redirect target is checked too."""
    apple.albums["B0z5qAGN1JIFd3y"].legacy_host = "p42-sharedstreams.evil.example"
    with pytest.raises(UntrustedHostError):
        await client(apple, LEGACY_URL).async_list()


async def test_not_found_and_login(apple: FakeApple) -> None:
    """Unknown albums and people-only albums get their own errors."""
    with pytest.raises(AlbumNotFoundError):
        await client(
            apple, "https://photos.icloud.com/shared/album/Nope12345"
        ).async_list()
    with pytest.raises(AlbumNotFoundError):
        await client(
            apple, "https://www.icloud.com/sharedalbum/#Nope12345"
        ).async_list()
    apple.add(FakeAlbum("Private123", "Private", requires_login=True))
    with pytest.raises(AlbumRequiresLoginError):
        await client(
            apple, "https://photos.icloud.com/shared/album/Private123"
        ).async_list()


async def test_repeated_marker_is_incomplete(apple: FakeApple) -> None:
    """A paging loop raises instead of returning a partial album."""
    apple.page_size = 1
    apple.repeat_marker = True
    with pytest.raises(IncompleteListingError):
        await client(apple).async_list()


async def test_retries_then_gives_up(apple: FakeApple) -> None:
    """429/5xx are retried; three failures in a row raise."""
    apple.status_queue = [429, 503]
    listing = await client(apple).async_list()
    assert len(listing.items) == 3
    apple.status_queue = [503, 503, 503]
    with pytest.raises(AppleApiError):
        await client(apple).async_list()


async def test_unexpected_status_and_bad_json(apple: FakeApple) -> None:
    """Other statuses are Apple errors."""
    apple.status_queue = [403]
    with pytest.raises(AppleApiError):
        await client(apple).async_list()


async def test_connection_errors_become_cannot_connect() -> None:
    """Network failures don't leak URLs or tokens in the message."""
    import aiohttp

    class Broken:
        def post(self, *args, **kwargs):
            raise aiohttp.ClientConnectionError(
                "https://x/?publicAccessAuthToken=secret"
            )

    with pytest.raises(CannotConnectError) as err:
        await SharedAlbumClient(Broken(), parse_link(MODERN_URL)).async_list()  # type: ignore[arg-type]
    assert "secret" not in str(err.value)


async def test_download_redirect_to_untrusted_host(apple: FakeApple) -> None:
    """Redirects are followed by hand and checked."""
    apple.redirect_downloads_to = "evil.example"
    with pytest.raises(UntrustedHostError):
        async with client(apple).open_download(
            "https://cvws.icloud-content.com/B/G1/Original/x"
        ):
            pass


async def test_download_errors(apple: FakeApple) -> None:
    """404 is a download error; 503 is retryable."""
    with pytest.raises(DownloadError):
        async with client(apple).open_download(
            "https://cvws.icloud-content.com/B/none/Original/x"
        ):
            pass
    apple.fail_download_times["G1"] = 1
    with pytest.raises(CannotConnectError):
        async with client(apple).open_download(
            "https://cvws.icloud-content.com/B/G1/Original/x"
        ):
            pass


def _asset(*derivatives: Derivative, video: bool = False) -> RemoteAsset:
    return RemoteAsset(
        "g", "video" if video else "image", "IMG", derivatives=list(derivatives)
    )


ORIG_HEIC = Derivative("Original", "u1", 4032, 3024, 3_000_000, "public.heic")
FULL_JPEG = Derivative("JPEGFull", "u2", 4032, 3024, 2_500_000, "public.jpeg")
MED_JPEG = Derivative("JPEGMed", "u3", 2048, 1536, 400_000, "public.jpeg")


def test_choose_largest_for_original_modes() -> None:
    """Originals and Convert take the largest; ties prefer Apple's original."""
    asset = _asset(MED_JPEG, FULL_JPEG, ORIG_HEIC)
    assert asset.choose(PhotoFormat.ORIGINAL) is ORIG_HEIC
    assert asset.choose(PhotoFormat.CONVERT) is ORIG_HEIC


def test_choose_convert_without_heic_support_falls_back_to_jpeg() -> None:
    """When HEIC can't be converted, the largest JPEG is used."""
    assert (
        _asset(MED_JPEG, FULL_JPEG, ORIG_HEIC).choose(
            PhotoFormat.CONVERT, heic_supported=False
        )
        is FULL_JPEG
    )
    assert (
        _asset(ORIG_HEIC).choose(PhotoFormat.CONVERT, heic_supported=False) is ORIG_HEIC
    )


def test_choose_dashboard() -> None:
    """Dashboard size uses Apple's medium JPEG, else a JPEG up to 2048 px."""
    assert _asset(ORIG_HEIC, MED_JPEG).choose(PhotoFormat.DASHBOARD) is MED_JPEG
    small = Derivative("1024", "u", 1024, 768, 100, "jpg")
    big = Derivative("2048", "u", 2048, 1536, 200, "jpg")
    assert _asset(small, big).choose(PhotoFormat.DASHBOARD) is big
    vmed = Derivative("VidMed", "v", 1280, 720, 10, "public.mpeg-4")
    vorig = Derivative("Original", "v", 1920, 1080, 20, "com.apple.quicktime-movie")
    assert _asset(vorig, vmed, video=True).choose(PhotoFormat.DASHBOARD) is vmed
    assert _asset(vorig, vmed, video=True).choose(PhotoFormat.ORIGINAL) is vorig


def test_choose_respects_minimums() -> None:
    """Renditions below the minimum size or edge are not used."""
    asset = _asset(MED_JPEG, ORIG_HEIC)
    assert asset.choose(PhotoFormat.DASHBOARD, min_long_edge=3000) is ORIG_HEIC
    assert asset.choose(PhotoFormat.ORIGINAL, min_bytes=10_000_000) is None


def test_extensions() -> None:
    """File types map to extensions."""
    assert ORIG_HEIC.extension == ".heic"
    assert MED_JPEG.extension == ".jpg"
    assert (
        Derivative("x", "u", file_type="com.apple.quicktime-movie").extension == ".mov"
    )
    assert Derivative("x", "u", file_type="public.mpeg-4").extension == ".mp4"
    assert Derivative("x", "u", file_type="public.png").extension == ".png"
    assert Derivative("x", "u", file_type="weird").extension == ""


def test_safe_stem() -> None:
    """Crafted filenames can't escape the folder."""
    assert safe_stem("../../etc/passwd", "guid123456789") == "passwd"
    assert safe_stem("..\\..\\win.ini", "guid123456789") == "win"
    assert safe_stem("", "guid123456789") == "icloud_guid12345678"
    assert safe_stem("我的照片.HEIC", "guid123456789") == "我的照片"
    assert safe_stem("Beach day!.jpg", "g") == "Beach day"
    assert safe_stem("a\x00b:c.jpg", "g") == "a_b_c"
    assert safe_stem("...", "guid123456789") == "icloud_guid12345678"


def test_cloudkit_records_skip_deleted_and_junk() -> None:
    """Deleted records, unknown types and masters without files are skipped."""
    records = [
        {"recordName": "X", "recordType": "CPLMaster", "deleted": True, "fields": {}},
        {"recordName": "Y", "recordType": "CPLMaster", "fields": {}},
        {"recordType": "CPLMaster", "fields": {}},
        "junk",
        {"recordName": "Z", "recordType": "Other", "fields": {}},
    ]
    assert parse_cloudkit_records(records) == []  # type: ignore[arg-type]


async def test_legacy_short_listing_is_incomplete(apple: FakeApple) -> None:
    """A legacy stream with fewer items than it claims is not trusted."""
    apple.items_returned_extra = 1
    with pytest.raises(IncompleteListingError):
        await client(apple, LEGACY_URL).async_list()
