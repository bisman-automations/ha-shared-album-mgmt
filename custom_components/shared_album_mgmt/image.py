"""Latest photo image entity: the newest photo in the album folder."""

from __future__ import annotations

from datetime import datetime
import mimetypes

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SharedAlbumConfigEntry
from .coordinator import AlbumCoordinator
from .entity import AlbumEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SharedAlbumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the image entity."""
    async_add_entities([LatestPhotoImage(hass, entry.runtime_data)])


class LatestPhotoImage(AlbumEntity, ImageEntity):
    """Serves the newest JPEG/PNG photo's bytes, read in the executor."""

    def __init__(self, hass: HomeAssistant, coordinator: AlbumCoordinator) -> None:
        """Set up both parents."""
        AlbumEntity.__init__(self, coordinator, "latest_photo")
        ImageEntity.__init__(self, hass)
        self._file: str | None = (
            coordinator.data.latest_file if coordinator.data else None
        )
        self._attr_image_last_updated = coordinator.latest_changed

    @callback
    def _handle_coordinator_update(self) -> None:
        latest = self.coordinator.data.latest_file
        if latest != self._file:
            self._file = latest
            self._attr_image_last_updated = (
                self.coordinator.latest_changed or datetime.now().astimezone()
            )
        super()._handle_coordinator_update()

    @property
    def content_type(self) -> str:  # type: ignore[override]
        """MIME type of the current file."""
        return mimetypes.guess_type(self._file or "x.jpg")[0] or "image/jpeg"

    async def async_image(self) -> bytes | None:
        """The current file's bytes, or None when there is no photo yet."""
        if not self._file:
            return None
        path = self.coordinator.target / self._file
        try:
            return await self.hass.async_add_executor_job(path.read_bytes)
        except OSError:
            return None
