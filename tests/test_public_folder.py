"""Album folders inside www/, which Home Assistant serves without a login."""

from __future__ import annotations

from pathlib import Path

from custom_components.shared_album_mgmt.const import DOMAIN
from custom_components.shared_album_mgmt.options import (
    async_validate_options,
    with_defaults,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .conftest import make_entry, setup_entry
from .fake_apple import FakeApple


def _public(hass: HomeAssistant, media_dir: Path) -> Path:
    www = Path(hass.config.path("www"))
    www.mkdir(parents=True, exist_ok=True)
    hass.config.media_dirs = {"local": str(media_dir), "web": str(www)}
    return www


async def test_a_new_folder_in_www_is_refused(
    hass: HomeAssistant, media_dir: Path
) -> None:
    _public(hass, media_dir)
    current = with_defaults(hass, "Family Photos", {})
    _, errors = await async_validate_options(
        hass, {"media_dir": "web", "folder": "icloud-albums/family"}, current
    )
    assert errors == {"folder": "public_folder"}
    cleaned, errors = await async_validate_options(
        hass, {"media_dir": "local", "folder": "shared_albums/family"}, current
    )
    assert errors == {}
    assert cleaned["media_dir"] == "local"


async def test_a_media_folder_linked_into_www_is_refused(
    hass: HomeAssistant, media_dir: Path
) -> None:
    www = _public(hass, media_dir)
    link = media_dir.parent / "linked"
    link.symlink_to(www)
    hass.config.media_dirs = {"local": str(media_dir), "linked": str(link)}
    current = with_defaults(hass, "Family Photos", {})
    _, errors = await async_validate_options(
        hass, {"media_dir": "linked", "folder": "family"}, current
    )
    assert errors == {"folder": "public_folder"}


async def test_an_album_already_in_www_keeps_working_with_a_repair(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    _public(hass, media_dir)
    entry = await setup_entry(hass, make_entry(media_dir="web", folder="albums/fam"))
    assert entry.state is ConfigEntryState.LOADED
    issue_id = f"public_folder_{entry.entry_id}"
    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_placeholders["album"] == "Family Photos"

    # Changing other settings of that album isn't refused.
    _, errors = await async_validate_options(
        hass, {"interval": 60}, with_defaults(hass, entry.title, entry.options)
    )
    assert "folder" not in errors

    # Moved to a media folder: the repair goes.
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "media_dir": "local", "folder": "fam"}
    )
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
