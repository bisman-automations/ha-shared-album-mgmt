"""Sensors: status, last sync, item count, bytes used, quarantine, last error."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SharedAlbumConfigEntry
from .coordinator import STATUS_ERROR, STATUS_IDLE, STATUS_SYNCING, AlbumSnapshot
from .entity import AlbumEntity

PARALLEL_UPDATES = 0

# Every error key a sync can record (plus "none"), for the enum sensor.
ERROR_STATES = [
    "none",
    "invalid_link",
    "album_not_found",
    "album_requires_login",
    "apple_error",
    "cannot_connect",
    "incomplete_listing",
    "untrusted_host",
    "low_disk_space",
    "download_failed",
    "storage_error",
    "unknown",
]


@dataclass(frozen=True, kw_only=True)
class AlbumSensorDescription(SensorEntityDescription):
    """How to read one sensor from the snapshot."""

    value: Callable[[AlbumSnapshot], Any]
    attrs: Callable[[AlbumSnapshot], dict[str, Any]] | None = None


SENSORS: tuple[AlbumSensorDescription, ...] = (
    AlbumSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=[STATUS_IDLE, STATUS_SYNCING, STATUS_ERROR],
        value=lambda s: s.status,
        attrs=lambda s: {"progress": s.progress} if s.progress else {},
    ),
    AlbumSensorDescription(
        key="last_sync",
        translation_key="last_sync",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda s: s.last_sync,
        attrs=lambda s: {"last_result": s.last_result} if s.last_result else {},
    ),
    AlbumSensorDescription(
        key="item_count",
        translation_key="item_count",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: s.item_count,
        attrs=lambda s: {"in_album": s.remote_count},
    ),
    AlbumSensorDescription(
        key="bytes_used",
        translation_key="bytes_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        suggested_display_precision=1,
        value=lambda s: s.bytes_used,
    ),
    AlbumSensorDescription(
        key="quarantine_count",
        translation_key="quarantine_count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda s: s.quarantine_count,
    ),
    AlbumSensorDescription(
        key="last_error",
        translation_key="last_error",
        device_class=SensorDeviceClass.ENUM,
        options=ERROR_STATES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda s: (
            s.last_error
            if s.last_error in ERROR_STATES
            else ("unknown" if s.last_error else "none")
        ),
        attrs=lambda s: dict(s.last_error_placeholders),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SharedAlbumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the album's sensors."""
    async_add_entities(AlbumSensor(entry.runtime_data, d) for d in SENSORS)


class AlbumSensor(AlbumEntity, SensorEntity):
    """One value from the album snapshot."""

    entity_description: AlbumSensorDescription

    def __init__(self, coordinator: Any, description: AlbumSensorDescription) -> None:
        """Bind the description."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | int | datetime | None:
        """The value."""
        return self.entity_description.value(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Extra detail (progress, last run, error details)."""
        if self.entity_description.attrs is None:
            return None
        return self.entity_description.attrs(self.coordinator.data)
