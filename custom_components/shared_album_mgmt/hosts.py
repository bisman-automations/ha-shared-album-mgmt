"""Which Apple hosts this integration is willing to talk to.

Apple's answers name the next host to call: public CloudKit returns a
"database partition" URL, the legacy sharedstreams API redirects to a
partition host, and both hand back download URLs on Apple's content CDN.
Following any host an answer names would let a tampered response point
Home Assistant anywhere, so every host is checked against an allow-list
first.

The CloudKit partition check accepts Apple's numbered partition hosts
(otherwise every new-style album fails with "Apple returned an invalid
public media endpoint"): Apple now returns numbered partition hosts
such as ``p51-ckdatabasews.icloud.com``. The ``pNN-`` part is a prefix on
the first label, not a subdomain, so a plain "is it ckdatabasews.icloud.com
or a subdomain of it" test rejected every new-style album. The patterns
below accept that prefix, a single subdomain label, and the China mirror
(``.com.cn``), and still reject look-alikes such as
``evilckdatabasews.icloud.com`` or ``ckdatabasews.icloud.com.evil.com``.

The same approach covers the legacy ``pNN-sharedstreams.icloud.com`` hosts
and the ``*.icloud-content.com`` download CDN. A user can add more hosts in
the album's advanced options, so a future Apple host change can be trusted
without waiting for a release.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
import re
from urllib.parse import urlparse

from .exceptions import UntrustedHostError


class HostKind(StrEnum):
    """What a host is used for. Shown in errors and the Repairs issue."""

    CLOUDKIT = "cloudkit"
    SHAREDSTREAMS = "sharedstreams"
    DOWNLOAD = "download"


# One optional "pNN-" prefix or one subdomain label, then Apple's host, then
# an optional China-mirror ".cn". re.fullmatch anchors both ends.
_CLOUDKIT = re.compile(r"(?:p[0-9]+-|[a-z0-9-]+\.)?ckdatabasews\.icloud\.com(?:\.cn)?")
_SHAREDSTREAMS = re.compile(
    r"(?:p[0-9]+-|[a-z0-9-]+\.)?sharedstreams\.icloud\.com(?:\.cn)?"
)
# Content hosts look like cvws.icloud-content.com or p123-...icloud-content.com.
# Any depth of subdomain is allowed under Apple's dedicated content domain.
_DOWNLOAD = re.compile(r"(?:[a-z0-9-]+\.)+icloud-content\.com(?:\.cn)?")

_PATTERNS: dict[HostKind, re.Pattern[str]] = {
    HostKind.CLOUDKIT: _CLOUDKIT,
    HostKind.SHAREDSTREAMS: _SHAREDSTREAMS,
    HostKind.DOWNLOAD: _DOWNLOAD,
}

# A hostname as typed into the advanced option: letters, digits, dots and
# hyphens, optionally with a leading "*." wildcard for one or more labels.
_EXTRA_HOST = re.compile(r"(\*\.)?([a-z0-9-]+\.)+[a-z]{2,}")


def normalize_extra_host(value: str) -> str | None:
    """Return a cleaned extra trusted host, or None when it isn't a hostname.

    Accepts a bare host (``p99-ckdatabasews.icloud.com``), a wildcard
    (``*.example-cdn.apple.com``) or a full URL, from which the host is
    taken. Hosts are lowercased and a trailing dot is dropped.
    """
    text = value.strip().lower()
    if not text:
        return None
    if "://" in text:
        text = (urlparse(text).hostname or "").lower()
    text = text.rstrip(".")
    if not _EXTRA_HOST.fullmatch(text):
        return None
    return text


def _matches_extra(host: str, extra: Iterable[str]) -> bool:
    """Match against user-added hosts. ``*.x`` matches subdomains of x only."""
    for item in extra:
        if item.startswith("*."):
            if host.endswith(item[1:]) and host != item[2:]:
                return True
        elif host == item:
            return True
    return False


def is_trusted_host(
    host: str | None, kind: HostKind, extra: Iterable[str] = ()
) -> bool:
    """Return whether ``host`` is an Apple host allowed for ``kind``."""
    if not host:
        return False
    host = host.lower().rstrip(".")
    return bool(_PATTERNS[kind].fullmatch(host)) or _matches_extra(host, extra)


def is_trusted_ckdatabase_host(host: str | None, extra: Iterable[str] = ()) -> bool:
    """Return whether ``host`` is a public CloudKit partition (numbered pNN- hosts included)."""
    return is_trusted_host(host, HostKind.CLOUDKIT, extra)


def require_trusted_url(url: str, kind: HostKind, extra: Iterable[str] = ()) -> str:
    """Return ``url`` when it is HTTPS on a trusted host, else raise.

    The error names the host so the log, the sensor and the Repairs issue
    can say exactly what Apple returned.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not is_trusted_host(host, kind, extra):
        raise UntrustedHostError(host or url[:80], kind.value)
    return url
