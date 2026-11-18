"""Parsing the public links Photos hands out."""

from __future__ import annotations

import pytest

from custom_components.shared_album_mgmt.const import LinkKind
from custom_components.shared_album_mgmt.exceptions import InvalidLinkError
from custom_components.shared_album_mgmt.links import parse_link, redact_id


@pytest.mark.parametrize(
    ("text", "kind", "album_id", "china"),
    [
        (
            "https://photos.icloud.com/shared/album/AbC12_-xyZ",
            LinkKind.MODERN,
            "AbC12_-xyZ",
            False,
        ),
        (
            "photos.icloud.com/shared/album/AbC12_-xyZ/",
            LinkKind.MODERN,
            "AbC12_-xyZ",
            False,
        ),
        (
            "  https://photos.icloud.com/shared/gallery/AbC12xyZ?ref=x ",
            LinkKind.MODERN,
            "AbC12xyZ",
            False,
        ),
        (
            "https://photos.icloud.com.cn/shared/album/AbC12xyZ",
            LinkKind.MODERN,
            "AbC12xyZ",
            True,
        ),
        (
            "https://www.icloud.com/sharedalbum/#B0z5qAGN1JIFd3y",
            LinkKind.LEGACY,
            "B0z5qAGN1JIFd3y",
            False,
        ),
        (
            "https://www.icloud.com/sharedalbum/en-us/#B0z5qAGN1JIFd3y",
            LinkKind.LEGACY,
            "B0z5qAGN1JIFd3y",
            False,
        ),
        (
            "icloud.com/sharedalbum/#B0z5qAGN1JIFd3y;CAEQARoQ",
            LinkKind.LEGACY,
            "B0z5qAGN1JIFd3y",
            False,
        ),
        (
            "https://www.icloud.com.cn/sharedalbum/#B0z5qAGN1JIFd3y",
            LinkKind.LEGACY,
            "B0z5qAGN1JIFd3y",
            True,
        ),
    ],
)
def test_valid_links(text: str, kind: LinkKind, album_id: str, china: bool) -> None:
    """Both link styles, with the variations apps add."""
    link = parse_link(text)
    assert link.kind is kind
    assert link.album_id == album_id
    assert link.china is china
    assert parse_link(link.url) == link
    assert link.unique_id == f"{kind.value}:{album_id}"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "hello",
        "https://photos.icloud.com/",
        "https://photos.icloud.com/shared/album/",
        "https://photos.icloud.com/shared/album/a/b",
        "https://www.icloud.com/sharedalbum/",
        "https://www.icloud.com/photos/#B0z5qAGN1JIFd3y",
        "https://evil.example/shared/album/AbC12xyZ",
        "https://photos.icloud.com.evil.example/shared/album/AbC12xyZ",
        "ftp://photos.icloud.com/shared/album/AbC12xyZ",
        "https://www.icloud.com/sharedalbum/#../../etc",
    ],
)
def test_invalid_links(text: str) -> None:
    """Anything else is refused."""
    with pytest.raises(InvalidLinkError):
        parse_link(text)


def test_redact_id() -> None:
    """Only a few characters of an id are ever shown."""
    assert redact_id("B0z5qAGN1JIFd3y") == "B0…3y"
    assert redact_id("abc") == "**REDACTED**"
