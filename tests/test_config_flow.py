"""Config, reconfigure and options flows."""

from __future__ import annotations

from pathlib import Path

import pytest

from custom_components.shared_album_mgmt.const import DOMAIN
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import LEGACY_URL, MODERN_ID, MODERN_URL, make_entry, setup_entry
from .fake_apple import FakeAlbum, FakeApple


async def _start(hass: HomeAssistant) -> dict:
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_full_flow_modern(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Paste link, pick settings, entry is created with defaults filled in."""
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": MODERN_URL, "advanced": {}}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"
    assert result["description_placeholders"] == {
        "album": "Family Photos",
        "photos": "2",
        "videos": "1",
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "media_dir": "local",
            "folder": "shared_albums/family_photos",
            "photo_format": "convert",
            "leave_mode": "quarantine",
            "interval_minutes": 60,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Family Photos"
    assert result["data"] == {
        "url": MODERN_URL,
        "kind": "modern",
        "album_id": MODERN_ID,
        "china": False,
    }
    options = result["options"]
    assert options["interval_minutes"] == 60
    assert options["leave_mode"] == "quarantine"
    assert options["sync_videos"] is True
    assert options["extra_trusted_hosts"] == []
    assert result["result"].unique_id == f"modern:{MODERN_ID}"
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (media_dir / "shared_albums/family_photos/IMG_0001.jpg").is_file()


async def test_legacy_link_and_custom_name(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Legacy links work; a typed name wins over Apple's."""
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": LEGACY_URL, "name": " Grandma ", "advanced": {}}
    )
    assert result["step_id"] == "settings"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "media_dir": "local",
            "folder": "shared_albums/grandma",
            "photo_format": "dashboard",
            "leave_mode": "keep",
            "interval_minutes": 0,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Grandma"
    assert result["data"]["kind"] == "legacy"
    assert result["options"]["interval_minutes"] == 0


@pytest.mark.parametrize(
    ("url", "setup", "error"),
    [
        ("https://example.com/nope", None, "invalid_link"),
        ("https://photos.icloud.com/shared/album/Missing123", None, "album_not_found"),
        (
            "https://photos.icloud.com/shared/album/Private123",
            "login",
            "album_requires_login",
        ),
        (MODERN_URL, "untrusted", "untrusted_host"),
        (MODERN_URL, "down", "apple_error"),
    ],
)
async def test_user_step_errors(
    hass: HomeAssistant,
    apple: FakeApple,
    media_dir: Path,
    url: str,
    setup: str | None,
    error: str,
) -> None:
    """Each failure shows its own message and keeps the form."""
    apple.add(FakeAlbum("Private123", "Private", requires_login=True))
    if setup == "untrusted":
        apple.albums[MODERN_ID].partition = "https://p51-ckdatabasews.icloud.example"
    if setup == "down":
        apple.status_queue = [503, 503, 503]
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": url, "advanced": {}}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}
    if setup == "untrusted":
        assert result["description_placeholders"] == {
            "host": "p51-ckdatabasews.icloud.example",
            "kind": "cloudkit",
        }


async def test_untrusted_host_can_be_trusted_in_the_flow(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """The user step's Advanced section takes extra hosts, which are saved."""
    apple.albums[MODERN_ID].partition = "https://p51-ckdatabasews.icloud.example"
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"url": MODERN_URL, "advanced": {"extra_trusted_hosts": ["not a host"]}},
    )
    assert result["errors"] == {"base": "invalid_host"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": MODERN_URL,
            "advanced": {"extra_trusted_hosts": ["P51-ckdatabasews.icloud.example"]},
        },
    )
    assert result["step_id"] == "settings"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "media_dir": "local",
            "folder": "a",
            "photo_format": "convert",
            "leave_mode": "quarantine",
            "interval_minutes": 180,
        },
    )
    assert result["options"]["extra_trusted_hosts"] == [
        "p51-ckdatabasews.icloud.example"
    ]


async def test_settings_errors(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Bad folder, unknown media dir and short intervals are refused."""
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": MODERN_URL, "advanced": {}}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "media_dir": "local",
            "folder": "../etc",
            "photo_format": "convert",
            "leave_mode": "quarantine",
            "interval_minutes": 5,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        "folder": "invalid_folder",
        "interval_minutes": "invalid_interval",
    }


async def test_already_configured(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """The same album can't be added twice, whatever the link's spelling."""
    make_entry().add_to_hass(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"url": f"photos.icloud.com/shared/album/{MODERN_ID}/?x=1", "advanced": {}},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_panel_step(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """The sidebar adds albums without a form; errors abort with their key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "panel"},
        data={"url": LEGACY_URL, "folder": "kids/album"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Old Album"
    assert result["options"]["folder"] == "kids/album"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "panel"}, data={"url": LEGACY_URL}
    )
    assert result["reason"] == "already_configured"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "panel"}, data={"url": "nope"}
    )
    assert result["reason"] == "invalid_link"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "panel"}, data={"url": MODERN_URL, "folder": "/../x"}
    )
    assert result["reason"] == "invalid_folder"
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_reconfigure(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Swap the link; a link for another existing album is refused."""
    entry = await setup_entry(hass, make_entry())
    other = make_entry(LEGACY_URL, "Old Album")
    other.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": LEGACY_URL}
    )
    assert result["reason"] == "already_configured"

    apple.add(FakeAlbum("NewAlbum123", "New"))
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": "nope"}
    )
    assert result["errors"] == {"base": "invalid_link"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": "https://photos.icloud.com/shared/album/NewAlbum123",
            "name": "Renamed",
        },
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.unique_id == "modern:NewAlbum123"
    assert entry.title == "Renamed"
    assert entry.data["album_id"] == "NewAlbum123"


def _options_input(**changes: object) -> dict:
    data = {
        "schedule": {"interval_minutes": 180},
        "content": {
            "sync_photos": True,
            "sync_videos": True,
            "photo_format": "convert",
            "leave_mode": "quarantine",
        },
        "storage": {
            "media_dir": "local",
            "folder": "shared_albums/family_photos",
            "write_latest": True,
            "write_index": True,
        },
        "limits": {
            "keep_days": 0,
            "max_files": 0,
            "min_file_size_kb": 0,
            "min_long_edge": 0,
        },
        "advanced": {
            "extra_trusted_hosts": [],
            "max_concurrent_downloads": 3,
            "min_free_space_mb": 500,
            "jpeg_quality": 90,
        },
    }
    for key, value in changes.items():
        section, field = key.split("__")
        data[section][field] = value
    return data


async def test_options_flow(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Sections are flattened on save; errors land on their section."""
    entry = await setup_entry(hass, make_entry())
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        _options_input(
            content__sync_photos=False,
            content__sync_videos=False,
            advanced__extra_trusted_hosts=["bad host"],
        ),
    )
    assert result["errors"] == {
        "content": "nothing_to_sync",
        "advanced": "invalid_host",
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        _options_input(
            content__leave_mode="delete",
            schedule__interval_minutes=0,
            advanced__extra_trusted_hosts=["*.cdn.example"],
        ),
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.options["leave_mode"] == "delete"
    assert entry.options["interval_minutes"] == 0
    assert entry.options["extra_trusted_hosts"] == ["*.cdn.example"]
    assert "content" not in entry.options
    assert entry.runtime_data.update_interval is None  # reloaded as manual
