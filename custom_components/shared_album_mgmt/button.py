"""Sync now button."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SharedAlbumConfigEntry
from .entity import AlbumEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SharedAlbumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the button."""
    async_add_entities([SyncNowButton(entry.runtime_data, "sync_now")])


class SyncNowButton(AlbumEntity, ButtonEntity):
    """Start a sync in the background (ignored while one is running)."""

    async def async_press(self) -> None:
        """Start the sync without waiting for it."""
        coordinator = self.coordinator
        if coordinator.syncing:
            return
        coordinator.config_entry.async_create_background_task(
            self.hass, coordinator.async_sync(), "shared_album_mgmt button sync"
        )
