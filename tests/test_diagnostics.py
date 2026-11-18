"""Diagnostics never contain the album link, id or tokens."""

from __future__ import annotations

import json
from pathlib import Path

from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from homeassistant.core import HomeAssistant

from .conftest import MODERN_ID, make_entry, setup_entry
from .fake_apple import FakeApple


async def test_diagnostics_redacted(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    apple: FakeApple,
    media_dir: Path,
) -> None:
    """The dump has counts and settings but no secrets."""
    entry = await setup_entry(hass, make_entry())
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    text = json.dumps(diag)
    assert MODERN_ID not in text
    assert "anon-token-secret" not in text
    assert "icloud-content.com" not in text
    assert diag["entry"]["data"]["url"] == "**REDACTED**"
    assert diag["entry"]["data"]["album_id"] == "**REDACTED**"
    assert diag["store"]["assets"] == 3
    assert diag["store"]["by_media_type"] == {"image": 2, "video": 1}
    assert diag["snapshot"]["status"] == "idle"
    assert diag["heic_available"] is True
