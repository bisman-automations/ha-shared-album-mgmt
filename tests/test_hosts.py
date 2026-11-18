"""The trusted-host allow-list, including numbered partition hosts."""

from __future__ import annotations

import pytest

from custom_components.shared_album_mgmt.exceptions import UntrustedHostError
from custom_components.shared_album_mgmt.hosts import (
    HostKind,
    is_trusted_ckdatabase_host,
    is_trusted_host,
    normalize_extra_host,
    require_trusted_url,
)


@pytest.mark.parametrize(
    "host",
    [
        "ckdatabasews.icloud.com",
        "p51-ckdatabasews.icloud.com",  # a numbered partition host
        "p1-ckdatabasews.icloud.com",
        "p123-ckdatabasews.icloud.com.cn",
        "a.ckdatabasews.icloud.com",
        "P51-CKDATABASEWS.ICLOUD.COM",  # hostnames are case-insensitive
        "p51-ckdatabasews.icloud.com.",  # trailing dot
    ],
)
def test_cloudkit_partition_hosts_accepted(host: str) -> None:
    """Apple's numbered partition hosts pass."""
    assert is_trusted_ckdatabase_host(host)


@pytest.mark.parametrize(
    "host",
    [
        "",
        None,
        "evilckdatabasews.icloud.com",
        "ckdatabasews.icloud.com.evil.com",
        "p51-ckdatabasews.icloud.com.evil.com",
        "a.b.ckdatabasews.icloud.com",
        "ckdatabasews.icloud.co",
        "pxx-ckdatabasews.icloud.com",
        "p51_ckdatabasews.icloud.com",
        "icloud.com",
        "p23-sharedstreams.icloud.com",
    ],
)
def test_cloudkit_lookalikes_rejected(host: str | None) -> None:
    """Look-alikes and other Apple services don't pass as CloudKit."""
    assert not is_trusted_ckdatabase_host(host)


@pytest.mark.parametrize(
    ("host", "ok"),
    [
        ("p23-sharedstreams.icloud.com", True),
        ("p42-sharedstreams.icloud.com.cn", True),
        ("sharedstreams.icloud.com", True),
        ("sharedstreams.icloud.com.evil.com", False),
        ("evilsharedstreams.icloud.com", False),
    ],
)
def test_sharedstreams_hosts(host: str, ok: bool) -> None:
    """Legacy partition hosts use the same rules."""
    assert is_trusted_host(host, HostKind.SHAREDSTREAMS) is ok


@pytest.mark.parametrize(
    ("host", "ok"),
    [
        ("cvws.icloud-content.com", True),
        ("p51-cvws.icloud-content.com", True),
        ("a.b.icloud-content.com", True),
        ("cvws.icloud-content.com.cn", True),
        ("icloud-content.com", False),
        ("cvws.icloud-content.com.evil.com", False),
        ("evil-icloud-content.com", False),
    ],
)
def test_download_hosts(host: str, ok: bool) -> None:
    """Downloads only come from Apple's content CDN."""
    assert is_trusted_host(host, HostKind.DOWNLOAD) is ok


def test_extra_hosts_and_wildcards() -> None:
    """User-added hosts extend each list; *.x matches subdomains only."""
    assert is_trusted_host(
        "p9-new.apple-cloud.example", HostKind.CLOUDKIT, ["p9-new.apple-cloud.example"]
    )
    assert is_trusted_host("a.cdn.example", HostKind.DOWNLOAD, ["*.cdn.example"])
    assert not is_trusted_host("cdn.example", HostKind.DOWNLOAD, ["*.cdn.example"])
    assert not is_trusted_host("evilcdn.example", HostKind.DOWNLOAD, ["*.cdn.example"])


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        (" P99-CKdatabasews.icloud.com ", "p99-ckdatabasews.icloud.com"),
        (
            "https://p99-ckdatabasews.icloud.com/database/1",
            "p99-ckdatabasews.icloud.com",
        ),
        ("*.icloud-content.com", "*.icloud-content.com"),
        ("host.example.", "host.example"),
        ("not a host", None),
        ("", None),
        ("localhost", None),
        ("*.", None),
    ],
)
def test_normalize_extra_host(raw: str, clean: str | None) -> None:
    """The advanced option accepts host names, wildcards and URLs."""
    assert normalize_extra_host(raw) == clean


def test_require_trusted_url_names_the_host() -> None:
    """The error says which host Apple returned and what for."""
    assert require_trusted_url(
        "https://p51-ckdatabasews.icloud.com/x", HostKind.CLOUDKIT
    )
    with pytest.raises(UntrustedHostError) as err:
        require_trusted_url("https://evil.example/x", HostKind.CLOUDKIT)
    assert err.value.host == "evil.example"
    assert err.value.kind == "cloudkit"
    assert "evil.example" in str(err.value)
    with pytest.raises(UntrustedHostError):
        require_trusted_url("http://p51-ckdatabasews.icloud.com/x", HostKind.CLOUDKIT)
