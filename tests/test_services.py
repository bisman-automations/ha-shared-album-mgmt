"""Actions: sync_now, rebuild_index and purge_quarantine."""

from __future__ import annotations

from pathlib import Path

import pytest

from custom_components.shared_album_mgmt.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import MODERN_ID, make_entry, setup_entry
from .fake_apple import FakeApple


async def test_sync_now(hass: HomeAssistant, apple: FakeApple, media_dir: Path) -> None:
    """sync_now starts a sync in the background."""
    entry = await setup_entry(hass, make_entry())
    apple.albums[MODERN_ID].items.append(
        FakeApple.photo("NEW", "NEW.JPG", 1_794_000_000_000)
    )
    await hass.services.async_call(
        DOMAIN,
        "sync_now",
        {"config_entry_id": entry.entry_id, "full": True},
        blocking=True,
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (media_dir / "shared_albums/family_photos/NEW.jpg").exists()


async def test_sync_now_errors(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Unknown, unloaded and busy albums are refused with a clear message."""
    entry = await setup_entry(hass, make_entry())
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, "sync_now", {"config_entry_id": "nope"}, blocking=True
        )
    assert err.value.translation_key == "unknown_album"
    async with entry.runtime_data._lock:
        with pytest.raises(ServiceValidationError) as err:
            await hass.services.async_call(
                DOMAIN, "sync_now", {"config_entry_id": entry.entry_id}, blocking=True
            )
        assert err.value.translation_key == "already_syncing"
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN,
                "rebuild_index",
                {"config_entry_id": entry.entry_id},
                blocking=True,
                return_response=True,
            )
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    # Services stay registered (async_setup), so the error is "not loaded".
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, "sync_now", {"config_entry_id": entry.entry_id}, blocking=True
        )
    assert err.value.translation_key == "album_not_loaded"


async def test_rebuild_index(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """rebuild_index forgets missing files and reports counts."""
    entry = await setup_entry(hass, make_entry())
    (media_dir / "shared_albums/family_photos/IMG_0003.mov").unlink()
    response = await hass.services.async_call(
        DOMAIN,
        "rebuild_index",
        {"config_entry_id": entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert response == {"forgotten": 1, "items": 2}


async def test_purge_quarantine(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """purge_quarantine deletes quarantined files, optionally by age."""
    entry = await setup_entry(hass, make_entry())
    album = apple.albums[MODERN_ID]
    album.items = album.items[:1]
    await entry.runtime_data.async_sync()
    assert entry.runtime_data.data.quarantine_count == 2
    response = await hass.services.async_call(
        DOMAIN,
        "purge_quarantine",
        {"config_entry_id": entry.entry_id, "older_than_days": 7},
        blocking=True,
        return_response=True,
    )
    assert response == {"deleted": 0}
    response = await hass.services.async_call(
        DOMAIN,
        "purge_quarantine",
        {"config_entry_id": entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert response == {"deleted": 2}
    assert not list((media_dir / "shared_albums/family_photos/.quarantine").iterdir())
    assert entry.runtime_data.data.quarantine_count == 0
