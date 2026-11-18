"""Base entity: one device per album."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import AlbumCoordinator


class AlbumEntity(CoordinatorEntity[AlbumCoordinator]):
    """An entity of one album. Stays available while the entry is loaded."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AlbumCoordinator, key: str) -> None:
        """Name the entity from its translation key and attach the device."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Apple iCloud",
            model="Public shared album",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="homeassistant://shared-album-mgmt",
            sw_version=NAME,
        )

    @property
    def available(self) -> bool:
        """Errors are reported by state, not by going unavailable."""
        return self.coordinator.data is not None
