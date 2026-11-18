"""No blocking file I/O on the event loop from this integration.

Wraps the low-level file functions and records any call made on the event
loop thread with a frame from ``custom_components/shared_album_mgmt`` on the
stack, then exercises setup, syncs, quarantine, the panel API, the media
view, and the image entity.
"""

from __future__ import annotations

import builtins
from collections.abc import Callable, Generator
import io
import os
from pathlib import Path
import shutil
import sys
import sysconfig
import threading
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.typing import (
    ClientSessionGenerator,
    WebSocketGenerator,
)

from custom_components.shared_album_mgmt.const import DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import MODERN_ID, make_entry, setup_entry
from .fake_apple import FakeApple

PACKAGE = os.sep.join(("custom_components", "shared_album_mgmt"))
STDLIB = sysconfig.get_paths()["stdlib"]


@pytest.fixture
def loop_io(hass: HomeAssistant) -> Generator[list[str]]:
    """Record file I/O done on the loop thread by the integration."""
    loop_thread = threading.get_ident()
    seen: list[str] = []

    def wrap(name: str, func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if threading.get_ident() == loop_thread:
                # The first frame outside the standard library is the caller.
                # asyncio debug mode reads source lines for task tracebacks
                # (linecache), which is the test harness, not the integration.
                frame = sys._getframe(1)
                debug_only = False
                while frame is not None and frame.f_code.co_filename.startswith(STDLIB):
                    debug_only |= frame.f_code.co_filename.endswith(
                        ("linecache.py", "traceback.py")
                    )
                    frame = frame.f_back
                if (
                    frame is not None
                    and not debug_only
                    and PACKAGE in frame.f_code.co_filename
                ):
                    seen.append(
                        f"{name} from {frame.f_code.co_filename}:{frame.f_lineno}"
                    )
            return func(*args, **kwargs)

        return wrapper

    targets = [
        (builtins, "open"),
        (io, "open"),
        (os, "open"),
        (os, "stat"),
        (os, "replace"),
        (os, "unlink"),
        (os, "scandir"),
        (os, "listdir"),
        (os, "mkdir"),
        (shutil, "copyfile"),
        (shutil, "disk_usage"),
    ]
    patches = [
        patch.object(mod, attr, wrap(f"{mod.__name__}.{attr}", getattr(mod, attr)))
        for mod, attr in targets
    ]
    for p in patches:
        p.start()
    try:
        yield seen
    finally:
        for p in patches:
            p.stop()


async def test_no_file_io_on_the_event_loop(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_client: ClientSessionGenerator,
    apple: FakeApple,
    media_dir: Path,
    loop_io: list[str],
) -> None:
    """Everything that touches disk runs in the executor."""
    entry = await setup_entry(hass, make_entry())
    album = apple.albums[MODERN_ID]
    album.items = album.items[:2]
    await entry.runtime_data.async_sync(verify=True)

    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id({"type": f"{DOMAIN}/subscribe"})
    await ws.receive_json()
    await ws.receive_json()
    await ws.send_json_auto_id({"type": f"{DOMAIN}/items", "entry_id": entry.entry_id})
    items = (await ws.receive_json())["result"]["items"]
    await ws.send_json_auto_id(
        {"type": f"{DOMAIN}/quarantine", "entry_id": entry.entry_id}
    )
    quarantined = (await ws.receive_json())["result"]["items"]
    client = await hass_client()
    await (await client.get(items[0]["thumb"])).read()
    await (await client.get(items[0]["full"])).read()
    await (await client.get(quarantined[0]["thumb"])).read()
    picture = hass.states.get("image.family_photos_latest_photo").attributes[
        "entity_picture"
    ]
    await (await client.get(picture)).read()
    await ws.send_json_auto_id(
        {
            "type": f"{DOMAIN}/restore",
            "entry_id": entry.entry_id,
            "ids": [quarantined[0]["id"]],
        }
    )
    await ws.receive_json()
    await hass.services.async_call(
        DOMAIN,
        "rebuild_index",
        {"config_entry_id": entry.entry_id},
        blocking=True,
        return_response=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "purge_quarantine",
        {"config_entry_id": entry.entry_id},
        blocking=True,
        return_response=True,
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert loop_io == []
