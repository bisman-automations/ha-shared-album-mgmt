"""Problem binary sensor: on when the last sync failed or files failed."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    """Add the problem sensor."""
    async_add_entities([AlbumProblemSensor(entry.runtime_data, "problem")])


class AlbumProblemSensor(AlbumEntity, BinarySensorEntity):
    """On when the album needs attention."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        """The last sync recorded an error."""
        return self.coordinator.data.problem

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Which error, and its details."""
        data = self.coordinator.data
        return {"error": data.last_error, **data.last_error_placeholders}
