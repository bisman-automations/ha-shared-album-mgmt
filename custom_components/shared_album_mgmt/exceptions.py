"""Errors raised while reading an album or syncing it.

Each error carries a ``translation_key`` so the config flow, the "Last error"
sensor and the sidebar panel can show the same plain-language message.
"""

from __future__ import annotations


class SharedAlbumError(Exception):
    """Base class for everything this integration raises on purpose."""

    translation_key = "unknown"

    def __init__(self, message: str | None = None) -> None:
        """Store a log-friendly message (never a token or a full album URL)."""
        super().__init__(message or self.translation_key)

    @property
    def placeholders(self) -> dict[str, str]:
        """Values for the translated message."""
        return {}


class InvalidLinkError(SharedAlbumError):
    """The text isn't a public iCloud shared album link."""

    translation_key = "invalid_link"


class AlbumNotFoundError(SharedAlbumError):
    """Apple doesn't know the album, or its Public Website was turned off."""

    translation_key = "album_not_found"


class AlbumRequiresLoginError(SharedAlbumError):
    """The album is shared with people only, not as a public website."""

    translation_key = "album_requires_login"


class AppleApiError(SharedAlbumError):
    """Apple answered with an error or something this code can't read."""

    translation_key = "apple_error"


class CannotConnectError(SharedAlbumError):
    """Apple couldn't be reached (network, DNS, timeout)."""

    translation_key = "cannot_connect"


class IncompleteListingError(SharedAlbumError):
    """The album listing stopped part way, so nothing may be removed."""

    translation_key = "incomplete_listing"


class UntrustedHostError(SharedAlbumError):
    """Apple pointed at a host that isn't on the allow-list."""

    translation_key = "untrusted_host"

    def __init__(self, host: str, kind: str) -> None:
        """Remember the host and what it was for."""
        self.host = host
        self.kind = kind
        super().__init__(f"Apple returned an unexpected {kind} host: {host}")

    @property
    def placeholders(self) -> dict[str, str]:
        """Name the host in the message."""
        return {"host": self.host, "kind": self.kind}


class LowDiskSpaceError(SharedAlbumError):
    """Downloading would leave less free space than the album allows."""

    translation_key = "low_disk_space"

    def __init__(self, free_mb: int, needed_mb: int) -> None:
        """Remember the numbers for the message."""
        self.free_mb = free_mb
        self.needed_mb = needed_mb
        super().__init__(f"Only {free_mb} MB free; {needed_mb} MB needed")

    @property
    def placeholders(self) -> dict[str, str]:
        """Free and needed space, in MB."""
        return {"free": str(self.free_mb), "needed": str(self.needed_mb)}


class DownloadError(SharedAlbumError):
    """A file couldn't be downloaded after every retry."""

    translation_key = "download_failed"
