"""The sidebar panel's websocket API, media view and panel registration."""

from __future__ import annotations

from http import HTTPStatus
import io
from pathlib import Path

from PIL import Image
from pytest_homeassistant_custom_component.typing import (
    ClientSessionGenerator,
    WebSocketGenerator,
)

from custom_components.shared_album_mgmt.const import DOMAIN, PANEL_URL
from homeassistant.core import HomeAssistant

from .conftest import LEGACY_URL, MODERN_ID, make_entry, setup_entry
from .fake_apple import FakeApple

PANELS = "frontend_panels"


async def test_subscribe_and_updates(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    apple: FakeApple,
    media_dir: Path,
) -> None:
    """The panel gets the album list, then an event whenever anything changes."""
    entry = await setup_entry(hass, make_entry())
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id({"type": f"{DOMAIN}/subscribe"})
    assert (await ws.receive_json())["success"]
    event = (await ws.receive_json())["event"]
    assert event["heic_available"] is True
    assert event["media_dirs"] == ["local"]
    (album,) = event["albums"]
    assert album["entry_id"] == entry.entry_id
    assert album["album_id"] == "B0…dR"
    assert MODERN_ID not in str(event)
    assert album["item_count"] == 3
    assert album["photo_count"] == 2
    assert album["video_count"] == 1
    assert album["status"] == "idle"
    assert album["interval"] == 180
    assert album["options"]["leave_mode"] == "quarantine"
    assert (
        album["media_content_id"]
        == "media-source://media_source/local/shared_albums/family_photos"
    )
    assert album["latest_thumb"].startswith(
        f"/api/shared_album_mgmt/media/{entry.entry_id}/asset/G1?"
    )
    assert "authSig=" in album["latest_thumb"]

    entry.runtime_data.async_publish()
    event = (await ws.receive_json())["event"]
    assert event["albums"][0]["entry_id"] == entry.entry_id


async def test_items_and_media_view(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_client_no_auth: ClientSessionGenerator,
    apple: FakeApple,
    media_dir: Path,
) -> None:
    """Items are paged and filtered; signed URLs serve thumbnails and files."""
    entry = await setup_entry(hass, make_entry())
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id(
        {"type": f"{DOMAIN}/items", "entry_id": entry.entry_id, "limit": 2}
    )
    result = (await ws.receive_json())["result"]
    assert result["total"] == 3
    assert [i["file"] for i in result["items"]] == ["IMG_0001.jpg", "IMG_0002.jpg"]
    await ws.send_json_auto_id(
        {"type": f"{DOMAIN}/items", "entry_id": entry.entry_id, "media": "video"}
    )
    videos = (await ws.receive_json())["result"]
    assert [i["file"] for i in videos["items"]] == ["IMG_0003.mov"]

    client = await hass_client_no_auth()
    thumb = await client.get(result["items"][0]["thumb"])
    assert thumb.status == HTTPStatus.OK
    image = Image.open(io.BytesIO(await thumb.read()))
    assert image.format == "JPEG"
    full = await client.get(result["items"][1]["full"])
    assert (
        await full.read()
        == (media_dir / "shared_albums/family_photos/IMG_0002.jpg").read_bytes()
    )
    # Videos have no thumbnail; the panel shows an icon.
    assert (
        await client.get(videos["items"][0]["thumb"])
    ).status == HTTPStatus.NO_CONTENT
    # Unsigned and unknown requests are refused.
    assert (
        await client.get(f"/api/shared_album_mgmt/media/{entry.entry_id}/asset/G1")
    ).status == HTTPStatus.UNAUTHORIZED

    await ws.send_json_auto_id({"type": f"{DOMAIN}/items", "entry_id": "nope"})
    assert (await ws.receive_json())["error"]["code"] == "not_found"


async def test_media_view_rejects_unknown_keys(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    apple: FakeApple,
    media_dir: Path,
) -> None:
    """Only files the store knows about are served."""
    entry = await setup_entry(hass, make_entry())
    client = await hass_client()
    for path in (
        f"/api/shared_album_mgmt/media/{entry.entry_id}/asset/nope",
        f"/api/shared_album_mgmt/media/{entry.entry_id}/other/G1",
        "/api/shared_album_mgmt/media/nope/asset/G1",
        f"/api/shared_album_mgmt/media/{entry.entry_id}/asset/..%2F..%2Fsecrets.yaml",
    ):
        # HA's security filter answers 400 for traversal attempts.
        assert (await client.get(path)).status in (
            HTTPStatus.NOT_FOUND,
            HTTPStatus.BAD_REQUEST,
        ), path


async def test_quarantine_restore_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    apple: FakeApple,
    media_dir: Path,
) -> None:
    """Review quarantine from the panel."""
    entry = await setup_entry(hass, make_entry())
    album = apple.albums[MODERN_ID]
    album.items = album.items[:1]
    await entry.runtime_data.async_sync()
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id(
        {"type": f"{DOMAIN}/quarantine", "entry_id": entry.entry_id}
    )
    items = (await ws.receive_json())["result"]["items"]
    assert {i["file"] for i in items} == {"IMG_0002.jpg", "IMG_0003.mov"}
    assert all(i["reason"] == "left_album" for i in items)
    by_file = {i["file"]: i["id"] for i in items}

    await ws.send_json_auto_id(
        {
            "type": f"{DOMAIN}/restore",
            "entry_id": entry.entry_id,
            "ids": [by_file["IMG_0002.jpg"], "nope"],
        }
    )
    assert (await ws.receive_json())["result"] == {"restored": ["IMG_0002.jpg"]}
    assert (media_dir / "shared_albums/family_photos/IMG_0002.jpg").exists()

    await ws.send_json_auto_id(
        {
            "type": f"{DOMAIN}/delete_quarantined",
            "entry_id": entry.entry_id,
            "ids": [by_file["IMG_0003.mov"]],
        }
    )
    assert (await ws.receive_json())["result"] == {"deleted": 1}
    assert entry.runtime_data.data.quarantine_count == 0


async def test_sync_command(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    apple: FakeApple,
    media_dir: Path,
) -> None:
    """Sync from the panel; a second request while busy says so."""
    entry = await setup_entry(hass, make_entry())
    ws = await hass_ws_client(hass)
    async with entry.runtime_data._lock:
        await ws.send_json_auto_id(
            {"type": f"{DOMAIN}/sync", "entry_id": entry.entry_id}
        )
        assert (await ws.receive_json())["result"] == {"started": False}
    await ws.send_json_auto_id(
        {"type": f"{DOMAIN}/sync", "entry_id": entry.entry_id, "full": True}
    )
    assert (await ws.receive_json())["result"] == {"started": True}
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_update_settings(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    apple: FakeApple,
    media_dir: Path,
) -> None:
    """Settings from the panel go through the same validation as the options flow."""
    entry = await setup_entry(hass, make_entry())
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id(
        {
            "type": f"{DOMAIN}/update_settings",
            "entry_id": entry.entry_id,
            "options": {
                "folder": "../../config",
                "interval_minutes": 3,
                "photo_format": "webp",
            },
        }
    )
    result = (await ws.receive_json())["result"]
    assert result == {
        "ok": False,
        "errors": {
            "folder": "invalid_folder",
            "interval_minutes": "invalid_interval",
            "photo_format": "invalid_choice",
        },
    }
    await ws.send_json_auto_id(
        {
            "type": f"{DOMAIN}/update_settings",
            "entry_id": entry.entry_id,
            "title": "Family",
            "options": {
                "leave_mode": "keep",
                "photo_format": "dashboard",
                "interval_minutes": 0,
                "bogus": 1,
            },
        }
    )
    result = (await ws.receive_json())["result"]
    assert result["ok"] is True
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.title == "Family"
    assert entry.options["leave_mode"] == "keep"
    assert entry.options["photo_format"] == "dashboard"
    assert "bogus" not in entry.options
    assert entry.runtime_data.update_interval is None


async def test_validate_and_add_album(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    apple: FakeApple,
    media_dir: Path,
) -> None:
    """Check a link, add it, and see it can't be added twice."""
    await setup_entry(hass, make_entry())
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id(
        {"type": f"{DOMAIN}/validate_link", "url": "https://nope.example"}
    )
    assert (await ws.receive_json())["result"] == {
        "ok": False,
        "error": "invalid_link",
        "placeholders": {},
    }

    await ws.send_json_auto_id({"type": f"{DOMAIN}/validate_link", "url": LEGACY_URL})
    result = (await ws.receive_json())["result"]
    assert result == {
        "ok": True,
        "kind": "legacy",
        "name": "Old Album",
        "photos": 1,
        "videos": 1,
        "already_added": False,
    }

    await ws.send_json_auto_id(
        {
            "type": f"{DOMAIN}/add_album",
            "url": LEGACY_URL,
            "name": "Grandma",
            "folder": "grandma",
        }
    )
    result = (await ws.receive_json())["result"]
    assert result["ok"] is True
    added = hass.config_entries.async_get_entry(result["entry_id"])
    assert added.title == "Grandma"
    assert added.options["folder"] == "grandma"
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (media_dir / "grandma/index.json").exists()

    await ws.send_json_auto_id({"type": f"{DOMAIN}/validate_link", "url": LEGACY_URL})
    assert (await ws.receive_json())["result"]["already_added"] is True
    await ws.send_json_auto_id({"type": f"{DOMAIN}/add_album", "url": LEGACY_URL})
    assert (await ws.receive_json())["result"] == {
        "ok": False,
        "error": "already_configured",
        "placeholders": {},
    }


async def test_add_album_with_trusted_host(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    apple: FakeApple,
    media_dir: Path,
) -> None:
    """An unknown host is reported; trusting it from the panel lets the add through."""
    await setup_entry(hass, make_entry(LEGACY_URL, "Old Album"))
    apple.albums[MODERN_ID].partition = "https://p77-ckdatabasews.icloud.example"
    ws = await hass_ws_client(hass)
    url = f"https://photos.icloud.com/shared/album/{MODERN_ID}"
    await ws.send_json_auto_id({"type": f"{DOMAIN}/validate_link", "url": url})
    result = (await ws.receive_json())["result"]
    assert result["error"] == "untrusted_host"
    assert result["placeholders"]["host"] == "p77-ckdatabasews.icloud.example"
    hosts = ["p77-ckdatabasews.icloud.example"]
    await ws.send_json_auto_id(
        {"type": f"{DOMAIN}/validate_link", "url": url, "extra_trusted_hosts": hosts}
    )
    assert (await ws.receive_json())["result"]["ok"] is True
    await ws.send_json_auto_id(
        {"type": f"{DOMAIN}/add_album", "url": url, "extra_trusted_hosts": hosts}
    )
    result = (await ws.receive_json())["result"]
    assert result["ok"] is True
    assert (
        hass.config_entries.async_get_entry(result["entry_id"]).options[
            "extra_trusted_hosts"
        ]
        == hosts
    )
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_remove_album_and_panel(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    apple: FakeApple,
    media_dir: Path,
) -> None:
    """The panel exists while albums do; removing keeps the photos."""
    entry = await setup_entry(hass, make_entry())
    assert PANEL_URL in hass.data[PANELS]
    assert hass.data[PANELS][PANEL_URL].require_admin
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id(
        {"type": f"{DOMAIN}/remove_album", "entry_id": entry.entry_id}
    )
    assert (await ws.receive_json())["result"] == {"ok": True}
    await hass.async_block_till_done()
    assert hass.config_entries.async_get_entry(entry.entry_id) is None
    assert PANEL_URL not in hass.data[PANELS]
    assert (media_dir / "shared_albums/family_photos/IMG_0001.jpg").exists()
    await ws.send_json_auto_id(
        {"type": f"{DOMAIN}/remove_album", "entry_id": entry.entry_id}
    )
    assert (await ws.receive_json())["error"]["code"] == "not_found"


async def test_admin_only(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
    apple: FakeApple,
    media_dir: Path,
) -> None:
    """Non-admin users can't use the panel API."""
    await setup_entry(hass, make_entry())
    ws = await hass_ws_client(hass, hass_read_only_access_token)
    await ws.send_json_auto_id({"type": f"{DOMAIN}/subscribe"})
    assert (await ws.receive_json())["error"]["code"] == "unauthorized"


async def test_static_panel_js_served(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    apple: FakeApple,
    media_dir: Path,
) -> None:
    """The panel bundle is served from the integration."""
    await setup_entry(hass, make_entry())
    panel = hass.data[PANELS][PANEL_URL]
    js_url = panel.config["_panel_custom"]["js_url"]
    assert js_url.startswith(f"/{DOMAIN}_static/shared-album-mgmt-panel.js?v=0.1.0")
    client = await hass_client()
    resp = await client.get(js_url.split("?")[0])
    assert resp.status == HTTPStatus.OK
    assert "shared-album-mgmt-panel" in await resp.text()
