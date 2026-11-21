"""Base entity: one device per album."""

from __future__ import annotations

from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import AlbumCoordinator


class AlbumEntity(CoordinatorEntity[AlbumCoordinator]):
    """An entity of one album. Stays available while the entry is loaded.

    The coordinator publishes about twice a second while a sync downloads
    (progress for the panel and the Status sensor). Each entity writes its
    state only when what it shows changed, so the others stay quiet.
    """

    _attr_has_entity_name = True
    _written: Any = None

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

    def _shown(self) -> Any:
        """What a state write would show: availability, state, attributes."""
        return (self.available, self.state, self.extra_state_attributes)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Write only when the state or attributes changed."""
        shown = self._shown()
        if self._written is not None and shown == self._written:
            return
        self._written = shown
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Errors are reported by state, not by going unavailable."""
        return self.coordinator.data is not None
