"""Parse the public link a user pastes from Photos.

Apple has two public-link styles and both are still handed out:

- ``https://photos.icloud.com/shared/album/<id>`` (also ``/shared/gallery/``
  and the ``photos.icloud.com.cn`` mirror). Read through public CloudKit.
- ``https://www.icloud.com/sharedalbum/#<id>`` (also ``icloud.com`` and
  ``.com.cn``). Read through the older sharedstreams web API.

The album id is the only secret-ish part of a link: anyone holding it can
see the album. It is stored in the config entry (which Home Assistant keeps
private) and is redacted from diagnostics and logs.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse

from .const import LinkKind
from .exceptions import InvalidLinkError

_MODERN_HOSTS = frozenset({"photos.icloud.com", "photos.icloud.com.cn"})
_LEGACY_HOSTS = frozenset(
    {"www.icloud.com", "icloud.com", "www.icloud.com.cn", "icloud.com.cn"}
)
_MODERN_PATH = re.compile(r"/shared/(?:album|gallery)/([A-Za-z0-9_-]+)/?")
_LEGACY_PATH = re.compile(r"/sharedalbum(?:/[a-z]{2}(?:-[a-z]{2})?)?/?")
_ID = re.compile(r"[A-Za-z0-9_-]{5,64}")


@dataclass(frozen=True, slots=True)
class AlbumLink:
    """A parsed public album link."""

    kind: LinkKind
    album_id: str
    china: bool = False

    @property
    def unique_id(self) -> str:
        """Config entry unique id: one entry per album."""
        return f"{self.kind.value}:{self.album_id}"

    @property
    def url(self) -> str:
        """The canonical link, rebuilt from the parts."""
        tld = "com.cn" if self.china else "com"
        if self.kind is LinkKind.MODERN:
            return f"https://photos.icloud.{tld}/shared/album/{self.album_id}"
        return f"https://www.icloud.{tld}/sharedalbum/#{self.album_id}"


def parse_link(text: str) -> AlbumLink:
    """Return the album behind ``text`` or raise :class:`InvalidLinkError`.

    Leading and trailing spaces, a missing ``https://`` and a ``?query`` are
    tolerated because Photos and messaging apps add or strip them.
    """
    value = (text or "").strip()
    if not value:
        raise InvalidLinkError("empty link")
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("https", "http"):
        raise InvalidLinkError("not a web link")

    if host in _MODERN_HOSTS:
        match = _MODERN_PATH.fullmatch(parsed.path)
        if match and _ID.fullmatch(match.group(1)):
            return AlbumLink(LinkKind.MODERN, match.group(1), host.endswith(".cn"))
        raise InvalidLinkError("photos.icloud.com link without an album id")

    if host in _LEGACY_HOSTS:
        album_id = parsed.fragment.strip().split(";")[0]
        if _LEGACY_PATH.fullmatch(parsed.path or "/") and _ID.fullmatch(album_id):
            return AlbumLink(LinkKind.LEGACY, album_id, host.endswith(".cn"))
        raise InvalidLinkError("icloud.com link without a #album id")

    raise InvalidLinkError("not an iCloud shared album link")


def redact_id(album_id: str) -> str:
    """Show only the first and last two characters of an album id."""
    if len(album_id) <= 6:
        return "**REDACTED**"
    return f"{album_id[:2]}…{album_id[-2:]}"
