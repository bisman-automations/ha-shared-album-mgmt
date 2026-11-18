"""Admin-only websocket API for the sidebar panel.

Every command requires an administrator. Album links are never sent to
the browser in full: the panel shows the link style and a shortened id.
Image URLs are short-lived signed paths to :mod:`.thumbs`.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import probatio

from homeassistant.components import websocket_api
from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    ConfigEntry,
    ConfigEntryChange,
    ConfigEntryState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .api import describe_error
from .const import (
    CONF_EXTRA_HOSTS,
    CONF_FOLDER,
    CONF_MEDIA_DIR,
    CONF_NAME,
    CONF_URL,
    DOMAIN,
    SIGNAL_UPDATED,
    SIGNED_PATH_SECONDS,
)
from .convert import heic_available
from .coordinator import AlbumCoordinator
from .exceptions import SharedAlbumError
from .hosts import normalize_extra_host
from .links import parse_link, redact_id
from .options import media_content_id, validate_options, with_defaults
from .thumbs import media_path

PAGE_MAX = 500


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    """Register every command once."""
    if hass.data[DOMAIN].get("ws"):
        return
    for command in (
        ws_subscribe,
        ws_items,
        ws_quarantine,
        ws_restore,
        ws_delete_quarantined,
        ws_sync,
        ws_update_settings,
        ws_validate_link,
        ws_add_album,
        ws_remove_album,
    ):
        websocket_api.async_register_command(hass, command)
    hass.data[DOMAIN]["ws"] = True


def _sign(hass: HomeAssistant, connection: ActiveConnection, path: str) -> str:
    return async_sign_path(
        hass,
        path,
        timedelta(seconds=SIGNED_PATH_SECONDS),
        refresh_token_id=connection.refresh_token_id,
    )


def _entries(hass: HomeAssistant) -> list[ConfigEntry]:
    return sorted(
        hass.config_entries.async_entries(DOMAIN), key=lambda e: e.title.casefold()
    )


def _album_payload(
    hass: HomeAssistant, connection: ActiveConnection, entry: ConfigEntry
) -> dict[str, Any]:
    """Everything the panel shows for one album."""
    base: dict[str, Any] = {
        "entry_id": entry.entry_id,
        "title": entry.title,
        "kind": entry.data.get("kind"),
        "album_id": redact_id(str(entry.data.get("album_id", ""))),
        "state": entry.state.value,
        "options": with_defaults(hass, entry.title, entry.options),
    }
    if entry.state is not ConfigEntryState.LOADED:
        return base
    coordinator: AlbumCoordinator = entry.runtime_data
    snap = coordinator.data
    state = coordinator.store.state
    latest = None
    if state.latest_guid and state.latest_guid in state.assets:
        latest = _sign(
            hass, connection, media_path(entry.entry_id, "asset", state.latest_guid)
        )
    base.update(
        {
            "album_name": state.album_name,
            "status": snap.status if snap else "idle",
            "syncing": coordinator.syncing,
            "item_count": snap.item_count if snap else 0,
            "remote_count": snap.remote_count if snap else 0,
            "bytes_used": snap.bytes_used if snap else 0,
            "quarantine_count": snap.quarantine_count if snap else 0,
            "photo_count": sum(
                1 for r in state.assets.values() if r.media_type == "image"
            ),
            "video_count": sum(
                1 for r in state.assets.values() if r.media_type == "video"
            ),
            "last_sync": snap.last_sync.isoformat()
            if snap and snap.last_sync
            else None,
            "last_attempt": state.last_attempt,
            "last_error": snap.last_error if snap else None,
            "last_error_placeholders": snap.last_error_placeholders if snap else {},
            "last_result": snap.last_result if snap else None,
            "progress": snap.progress if snap else None,
            "interval": coordinator.update_interval.total_seconds() // 60
            if coordinator.update_interval
            else 0,
            "folder": str(coordinator.target),
            "media_content_id": media_content_id(coordinator.options),
            "latest_thumb": latest,
            "baseline": state.baseline,
            "pending_removal": len(state.pending_removal),
        }
    )
    return base


def _payload(hass: HomeAssistant, connection: ActiveConnection) -> dict[str, Any]:
    return {
        "albums": [_album_payload(hass, connection, e) for e in _entries(hass)],
        "heic_available": heic_available(),
        "media_dirs": sorted(hass.config.media_dirs),
    }


def _loaded(hass: HomeAssistant, entry_id: str) -> AlbumCoordinator | None:
    entry = hass.config_entries.async_get_entry(entry_id)
    if (
        entry is None
        or entry.domain != DOMAIN
        or entry.state is not ConfigEntryState.LOADED
    ):
        return None
    coordinator: AlbumCoordinator = entry.runtime_data
    return coordinator


@websocket_api.websocket_command({probatio.Required("type"): f"{DOMAIN}/subscribe"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_subscribe(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Stream the album list: the result first, then an event per change."""

    @callback
    def forward(_entry_id: str | None = None) -> None:
        connection.send_message(
            websocket_api.event_message(msg["id"], _payload(hass, connection))
        )

    @callback
    def entry_changed(_change: ConfigEntryChange, entry: ConfigEntry) -> None:
        if entry.domain == DOMAIN:
            forward()

    unsub_signal = async_dispatcher_connect(hass, SIGNAL_UPDATED, forward)
    unsub_entries = async_dispatcher_connect(
        hass, SIGNAL_CONFIG_ENTRY_CHANGED, entry_changed
    )

    @callback
    def unsubscribe() -> None:
        unsub_signal()
        unsub_entries()

    connection.subscriptions[msg["id"]] = unsubscribe
    connection.send_result(msg["id"])
    forward()


@websocket_api.websocket_command(
    {
        probatio.Required("type"): f"{DOMAIN}/items",
        probatio.Required("entry_id"): str,
        probatio.Optional("offset", default=0): probatio.All(
            int, probatio.Range(min=0)
        ),
        probatio.Optional("limit", default=120): probatio.All(
            int, probatio.Range(min=1, max=PAGE_MAX)
        ),
        probatio.Optional("media", default="all"): probatio.In(
            ["all", "image", "video"]
        ),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_items(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """A page of the album's files, newest first, with signed image URLs."""
    coordinator = _loaded(hass, msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "not_found", "Album not loaded")
        return
    records = sorted(
        (
            (guid, r)
            for guid, r in coordinator.store.state.assets.items()
            if msg["media"] == "all" or r.media_type == msg["media"]
        ),
        key=lambda kv: kv[1].captured_at or "",
        reverse=True,
    )
    page = records[msg["offset"] : msg["offset"] + msg["limit"]]
    entry_id = msg["entry_id"]
    connection.send_result(
        msg["id"],
        {
            "total": len(records),
            "items": [
                {
                    "guid": guid,
                    "file": r.file,
                    "media_type": r.media_type,
                    "captured_at": r.captured_at,
                    "size": r.size,
                    "width": r.width,
                    "height": r.height,
                    "in_album": r.in_album,
                    "pinned": r.pinned,
                    "contributor": r.contributor,
                    "caption": r.caption,
                    "thumb": _sign(
                        hass, connection, media_path(entry_id, "asset", guid)
                    ),
                    "full": _sign(
                        hass, connection, media_path(entry_id, "asset", guid, "full")
                    ),
                }
                for guid, r in page
            ],
        },
    )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): f"{DOMAIN}/quarantine",
        probatio.Required("entry_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_quarantine(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Quarantined files, most recently moved first."""
    coordinator = _loaded(hass, msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "not_found", "Album not loaded")
        return
    entry_id = msg["entry_id"]
    items = sorted(
        coordinator.store.state.quarantine.items(),
        key=lambda kv: kv[1].moved_at,
        reverse=True,
    )
    connection.send_result(
        msg["id"],
        {
            "items": [
                {
                    "id": qid,
                    "file": q.file,
                    "media_type": q.media_type,
                    "captured_at": q.captured_at,
                    "moved_at": q.moved_at,
                    "size": q.size,
                    "reason": q.reason,
                    "thumb": _sign(
                        hass, connection, media_path(entry_id, "quarantine", qid)
                    ),
                    "full": _sign(
                        hass,
                        connection,
                        media_path(entry_id, "quarantine", qid, "full"),
                    ),
                }
                for qid, q in items
            ]
        },
    )


_IDS: dict[Any, Any] = {
    probatio.Required("entry_id"): str,
    probatio.Required("ids"): probatio.All([str], probatio.Length(min=1, max=1000)),
}


@websocket_api.websocket_command(
    {probatio.Required("type"): f"{DOMAIN}/restore", **_IDS}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_restore(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Move quarantined files back into the album folder (kept for good)."""
    coordinator = _loaded(hass, msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "not_found", "Album not loaded")
        return
    restored = []
    for qid in msg["ids"]:
        if qid in coordinator.store.state.quarantine:
            restored.append(await coordinator.syncer.async_restore(qid))
    coordinator.async_publish()
    connection.send_result(msg["id"], {"restored": restored})


@websocket_api.websocket_command(
    {probatio.Required("type"): f"{DOMAIN}/delete_quarantined", **_IDS}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_delete_quarantined(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete quarantined files for good."""
    coordinator = _loaded(hass, msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "not_found", "Album not loaded")
        return
    deleted = await coordinator.syncer.async_delete_quarantined(list(msg["ids"]))
    coordinator.async_publish()
    connection.send_result(msg["id"], {"deleted": deleted})


@websocket_api.websocket_command(
    {
        probatio.Required("type"): f"{DOMAIN}/sync",
        probatio.Required("entry_id"): str,
        probatio.Optional("full", default=False): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_sync(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Start a sync in the background."""
    coordinator = _loaded(hass, msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "not_found", "Album not loaded")
        return
    if coordinator.syncing:
        connection.send_result(msg["id"], {"started": False})
        return
    coordinator.config_entry.async_create_background_task(
        hass, coordinator.async_sync(verify=msg["full"]), f"{DOMAIN} panel sync"
    )
    connection.send_result(msg["id"], {"started": True})


@websocket_api.websocket_command(
    {
        probatio.Required("type"): f"{DOMAIN}/update_settings",
        probatio.Required("entry_id"): str,
        probatio.Required("options"): dict,
        probatio.Optional("title"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_update_settings(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Validate and save an album's settings (the album reloads)."""
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN:
        connection.send_error(msg["id"], "not_found", "Album not found")
        return
    current = with_defaults(hass, entry.title, entry.options)
    cleaned, errors = validate_options(hass, msg["options"], current)
    title = (msg.get("title") or entry.title).strip() or entry.title
    if errors:
        connection.send_result(msg["id"], {"ok": False, "errors": errors})
        return
    hass.config_entries.async_update_entry(entry, options=cleaned, title=title)
    connection.send_result(msg["id"], {"ok": True, "options": cleaned})


async def _probe(
    hass: HomeAssistant, url: str, hosts: list[str] | None = None
) -> dict[str, Any]:
    """Check a link like the config flow does."""
    from .config_flow import async_probe  # noqa: PLC0415 - avoid a cycle

    link = parse_link(url)
    cleaned = [h for h in (normalize_extra_host(x) for x in hosts or []) if h]
    listing = await async_probe(hass, link, tuple(cleaned))
    photos = sum(1 for i in listing.items if not i.is_video)
    return {
        "kind": link.kind.value,
        "name": listing.name,
        "photos": photos,
        "videos": len(listing.items) - photos,
        "unique_id": link.unique_id,
    }


@websocket_api.websocket_command(
    {
        probatio.Required("type"): f"{DOMAIN}/validate_link",
        probatio.Required(CONF_URL): str,
        probatio.Optional(CONF_EXTRA_HOSTS): [str],
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_validate_link(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Read an album without adding it, so the panel can preview it."""
    try:
        result = await _probe(hass, msg[CONF_URL], msg.get(CONF_EXTRA_HOSTS))
    except SharedAlbumError as err:
        key, placeholders = describe_error(err)
        connection.send_result(
            msg["id"], {"ok": False, "error": key, "placeholders": placeholders}
        )
        return
    existing = {e.unique_id for e in hass.config_entries.async_entries(DOMAIN)}
    unique_id = result.pop("unique_id")
    connection.send_result(
        msg["id"], {"ok": True, **result, "already_added": unique_id in existing}
    )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): f"{DOMAIN}/add_album",
        probatio.Required(CONF_URL): str,
        probatio.Optional(CONF_NAME): str,
        probatio.Optional(CONF_MEDIA_DIR): str,
        probatio.Optional(CONF_FOLDER): str,
        probatio.Optional(CONF_EXTRA_HOSTS): [str],
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_add_album(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Add an album through the config flow's ``panel`` step."""
    data = {
        k: msg[k]
        for k in (CONF_URL, CONF_NAME, CONF_MEDIA_DIR, CONF_FOLDER, CONF_EXTRA_HOSTS)
        if k in msg
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "panel"}, data=data
    )
    if result["type"] is FlowResultType.CREATE_ENTRY:
        connection.send_result(
            msg["id"], {"ok": True, "entry_id": result["result"].entry_id}
        )
        return
    reason = (
        result.get("reason") or (result.get("errors") or {}).get("base") or "unknown"
    )
    connection.send_result(
        msg["id"],
        {
            "ok": False,
            "error": reason,
            "placeholders": result.get("description_placeholders") or {},
        },
    )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): f"{DOMAIN}/remove_album",
        probatio.Required("entry_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_remove_album(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Remove an album. Its folder and photos stay on disk."""
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN:
        connection.send_error(msg["id"], "not_found", "Album not found")
        return
    await hass.config_entries.async_remove(entry.entry_id)
    connection.send_result(msg["id"], {"ok": True})
