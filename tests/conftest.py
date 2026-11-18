"""Fixtures for Shared Album Mgmt tests."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shared_album_mgmt.const import DOMAIN
from custom_components.shared_album_mgmt.links import parse_link
from homeassistant.core import HomeAssistant

from .fake_apple import FakeAlbum, FakeApple

MODERN_ID = "B0zGWZuqDGuWcdR"
LEGACY_ID = "B0z5qAGN1JIFd3y"
MODERN_URL = f"https://photos.icloud.com/shared/album/{MODERN_ID}"
LEGACY_URL = f"https://www.icloud.com/sharedalbum/#{LEGACY_ID}"
DAY = 86_400_000
NOW_MS = 1_793_000_000_000  # 2026-10-26


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: Generator[None],
) -> Generator[None]:
    """Load custom integrations for every test."""
    yield


@pytest.fixture(autouse=True)
def no_backoff() -> Generator[None]:
    """Retries without waiting."""
    with (
        patch("custom_components.shared_album_mgmt.api.BACKOFF_SECONDS", 0),
        patch("custom_components.shared_album_mgmt.sync.BACKOFF_SECONDS", 0),
    ):
        yield


@pytest.fixture
def apple() -> Generator[FakeApple]:
    """The fake Apple session, used everywhere a session is asked for."""
    fake = FakeApple()
    fake.add(
        FakeAlbum(
            MODERN_ID,
            "Family Photos",
            [
                FakeApple.photo("G1", "IMG_0001.HEIC", NOW_MS, heic=True),
                FakeApple.photo(
                    "G2", "IMG_0002.JPG", NOW_MS - DAY, color=(20, 20, 200)
                ),
                FakeApple.video("G3", "IMG_0003.MOV", NOW_MS - 2 * DAY),
            ],
        )
    )
    fake.add(
        FakeAlbum(
            LEGACY_ID,
            "Old Album",
            [
                FakeApple.photo("L1", "x", NOW_MS),
                FakeApple.video("L2", "y", NOW_MS - DAY),
            ],
        )
    )
    with (
        patch(
            "custom_components.shared_album_mgmt.coordinator.async_get_clientsession",
            return_value=fake,
        ),
        patch(
            "custom_components.shared_album_mgmt.config_flow.async_get_clientsession",
            return_value=fake,
        ),
    ):
        yield fake


@pytest.fixture
def media_dir(hass: HomeAssistant, tmp_path: Path) -> Path:
    """A temporary media directory registered as 'local'."""
    path = tmp_path / "media"
    path.mkdir()
    hass.config.media_dirs = {"local": str(path)}
    return path


def make_entry(
    url: str = MODERN_URL, title: str = "Family Photos", **options: object
) -> MockConfigEntry:
    """A config entry for an album, with options overriding the defaults."""
    link = parse_link(url)
    return MockConfigEntry(
        domain=DOMAIN,
        title=title,
        unique_id=link.unique_id,
        data={
            "url": link.url,
            "kind": link.kind.value,
            "album_id": link.album_id,
            "china": False,
        },
        options={
            "folder": f"shared_albums/{title.lower().replace(' ', '_')}",
            "media_dir": "local",
            **options,
        },
    )


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    """Add and set up an entry, then wait for the first sync."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry
