"""Setup, unload, persistence and option helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from custom_components.shared_album_mgmt.options import (
    clean_folder,
    media_content_id,
    resolve_target,
    validate_options,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import make_entry, setup_entry
from .fake_apple import FakeApple


async def test_bad_folder_fails_setup(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """A stored folder outside the media dir stops setup with a clear error."""
    entry = make_entry(folder="../../config")
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    entry2 = make_entry(
        "https://photos.icloud.com/shared/album/Other12345", "Other", media_dir="nope"
    )
    entry2.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry2.entry_id)
    assert entry2.state is ConfigEntryState.SETUP_ERROR


async def test_setup_does_not_wait_for_apple(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Setup succeeds even when Apple is down; the error shows on the album."""
    apple.status_queue = [503] * 10
    entry = await setup_entry(hass, make_entry())
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.data.last_error == "apple_error"


async def test_state_survives_reload(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """The store keeps records, quarantine and the baseline across restarts."""
    entry = await setup_entry(hass, make_entry(interval_minutes=0))
    album = apple.albums["B0zGWZuqDGuWcdR"]
    album.items = album.items[:2]
    await entry.runtime_data.async_sync()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = entry.runtime_data.store.state
    assert state.baseline is True
    assert len(state.assets) == 2
    assert len(state.quarantine) == 1
    assert state.album_name == "Family Photos"


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("shared_albums/family", "shared_albums/family"),
        ("/shared_albums/family/", "shared_albums/family"),
        ("a\\b", "a/b"),
        ("Family Photos 2026", "Family Photos 2026"),
        ("..", None),
        ("a/../b", None),
        (".hidden", None),
        ("a/.quarantine", None),
        ("", None),
        ("   ", None),
        ("a/-b", None),
    ],
)
def test_clean_folder(raw: str, clean: str | None) -> None:
    """Folders can't climb out or hide."""
    assert clean_folder(raw) == clean


def test_resolve_target_and_media_id(hass: HomeAssistant, media_dir: Path) -> None:
    """Targets live under the chosen media dir."""
    assert (
        resolve_target(hass, {"media_dir": "local", "folder": "x/y"})
        == media_dir / "x/y"
    )
    with pytest.raises(ValueError, match="media_dir"):
        resolve_target(hass, {"media_dir": "nope", "folder": "x"})
    with pytest.raises(ValueError, match="folder"):
        resolve_target(hass, {"media_dir": "local", "folder": ".."})
    assert (
        media_content_id({"media_dir": "local", "folder": "x"}, "a.jpg")
        == "media-source://media_source/local/x/a.jpg"
    )


def test_validate_options(hass: HomeAssistant, media_dir: Path) -> None:
    """Numbers are coerced, unknown keys dropped and hosts normalised."""
    current = {
        "interval_minutes": 180,
        "sync_photos": True,
        "sync_videos": True,
        "photo_format": "convert",
        "leave_mode": "quarantine",
        "media_dir": "local",
        "folder": "a",
        "keep_days": 0,
        "max_files": 0,
        "min_file_size_kb": 0,
        "min_long_edge": 0,
        "write_latest": True,
        "write_index": True,
        "extra_trusted_hosts": [],
        "max_concurrent_downloads": 3,
        "min_free_space_mb": 500,
        "jpeg_quality": 90,
    }
    merged, errors = validate_options(
        hass,
        {
            "interval_minutes": "60",
            "max_files": 10.0,
            "extra_trusted_hosts": "a.example, *.b.example a.example",
            "x": 1,
        },
        current,
    )
    assert errors == {}
    assert merged["interval_minutes"] == 60
    assert merged["max_files"] == 10
    assert merged["extra_trusted_hosts"] == ["a.example", "*.b.example"]
    assert "x" not in merged
    _, errors = validate_options(
        hass,
        {
            "interval_minutes": 20000,
            "max_concurrent_downloads": 9,
            "jpeg_quality": 10,
            "keep_days": "x",
        },
        current,
    )
    assert errors == {
        "interval_minutes": "invalid_interval",
        "max_concurrent_downloads": "invalid_number",
        "jpeg_quality": "invalid_number",
        "keep_days": "invalid_number",
    }
