"""Sensors, the problem binary sensor, the Sync now button and the image."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.shared_album_mgmt.sensor import AlbumSensor
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .conftest import MODERN_ID, make_entry, setup_entry
from .fake_apple import FakeApple


async def test_entity_states(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """States after a good first sync."""
    await setup_entry(hass, make_entry())
    assert hass.states.get("sensor.family_photos_status").state == "idle"
    assert hass.states.get("sensor.family_photos_items").state == "3"
    assert hass.states.get("sensor.family_photos_last_sync").state not in (
        "unknown",
        "unavailable",
    )
    used = float(hass.states.get("sensor.family_photos_space_used").state)
    assert used > 0
    assert hass.states.get("sensor.family_photos_quarantined").state == "0"
    assert hass.states.get("sensor.family_photos_last_error").state == "none"
    assert hass.states.get("binary_sensor.family_photos_problem").state == "off"


async def test_error_states(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """A failed sync shows up as a problem with its reason, not unavailable."""
    apple.albums[MODERN_ID].partition = "https://evil.example"
    await setup_entry(hass, make_entry())
    assert hass.states.get("sensor.family_photos_status").state == "error"
    assert hass.states.get("sensor.family_photos_last_error").state == "untrusted_host"
    assert hass.states.get("binary_sensor.family_photos_problem").state == "on"


async def test_button_syncs(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Pressing Sync now picks up new photos."""
    await setup_entry(hass, make_entry())
    apple.albums[MODERN_ID].items.append(
        FakeApple.photo("NEW", "NEW.JPG", 1_794_000_000_000)
    )
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.family_photos_sync_now"}, blocking=True
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("sensor.family_photos_items").state == "4"


async def test_latest_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    apple: FakeApple,
    media_dir: Path,
) -> None:
    """The image entity serves the newest photo."""
    await setup_entry(hass, make_entry())
    state = hass.states.get("image.family_photos_latest_photo")
    assert state is not None and state.state not in ("unknown", "unavailable")
    client = await hass_client()
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == (media_dir / "shared_albums/family_photos/IMG_0001.jpg").read_bytes()
    assert resp.content_type == "image/jpeg"


async def test_unload_and_reload(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Unloading removes entities' availability; files stay; removal keeps files."""
    entry = await setup_entry(hass, make_entry())
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.family_photos_items").state == "unavailable"
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert (media_dir / "shared_albums/family_photos/IMG_0001.jpg").exists()


async def test_unchanged_entities_are_not_written(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Progress pushes write the Status sensor only, not every entity."""
    entry = await setup_entry(hass, make_entry())
    coordinator = entry.runtime_data
    written: list[str] = []
    original = Entity._async_write_ha_state

    def spy(self: Entity) -> None:
        written.append(self.entity_id)
        original(self)

    with patch.object(Entity, "_async_write_ha_state", spy):
        coordinator.async_publish()
        assert written == []

        coordinator._progress = {"done": 1, "total": 3, "current": "IMG_0002.jpg"}
        coordinator.async_publish()
        assert written == ["sensor.family_photos_status"]
    state = hass.states.get("sensor.family_photos_status")
    assert state.attributes["progress"]["done"] == 1
    # Shown live, but kept out of history.
    assert "progress" in AlbumSensor._unrecorded_attributes
