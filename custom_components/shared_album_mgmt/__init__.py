"""Shared Album Mgmt: keep public iCloud shared albums in a media folder.

Each config entry is one public shared album. It is synced on a schedule
into a folder under a Home Assistant media directory, so it appears in the
Media browser and can feed dashboards and slideshows. An admin-only sidebar
panel shows every album, its progress, its photos and its quarantine, and
edits its settings.
"""

from __future__ import annotations

import logging
from typing import Any

import probatio

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ConfigEntryError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .catalog import async_write_catalog
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_FULL,
    ATTR_OLDER_THAN_DAYS,
    CONF_ALBUM_ID,
    CONF_KIND,
    DOMAIN,
    SERVICE_PURGE_QUARANTINE,
    SERVICE_REBUILD_INDEX,
    SERVICE_SYNC_NOW,
    LinkKind,
)
from .convert import heic_available
from .coordinator import AlbumCoordinator
from .links import AlbumLink
from .options import with_defaults
from .panel import async_register_panel, async_register_static, async_unregister_panel
from .thumbs import async_register_views
from .websocket_api import async_register_websocket

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.IMAGE,
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type SharedAlbumConfigEntry = ConfigEntry[AlbumCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the panel script, the websocket API, views and services."""
    hass.data.setdefault(DOMAIN, {})
    # Import pillow-heif in the executor once, so later checks from the
    # event loop only read the cached answer.
    await hass.async_add_executor_job(heic_available)
    async_register_websocket(hass)
    async_register_views(hass)
    await async_register_static(hass)
    _async_register_services(hass)
    return True


def album_link(entry: ConfigEntry) -> AlbumLink:
    """The album a config entry syncs."""
    return AlbumLink(
        LinkKind(entry.data[CONF_KIND]),
        entry.data[CONF_ALBUM_ID],
        bool(entry.data.get("china", False)),
    )


async def async_setup_entry(hass: HomeAssistant, entry: SharedAlbumConfigEntry) -> bool:
    """Start an album: load its store, add entities, sync in the background."""
    options = with_defaults(hass, entry.title, entry.options)
    try:
        coordinator = AlbumCoordinator(hass, entry, album_link(entry), options)
    except ValueError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_folder_setup",
            translation_placeholders={"field": str(err)},
        ) from err
    await coordinator.async_load()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await async_register_panel(hass)
    entry.async_create_background_task(
        hass, coordinator.async_sync(), f"{DOMAIN} first sync {entry.entry_id}"
    )
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload so the new schedule, folder and filters take effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: SharedAlbumConfigEntry
) -> bool:
    """Stop an album. The panel goes away with the last album."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.store.async_save()
        others = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != entry.entry_id and e.state is ConfigEntryState.LOADED
        ]
        if not others:
            async_unregister_panel(hass)
        await async_write_catalog(hass)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Forget the album's records. Its folder and photos are left on disk."""
    from .store import AlbumStore  # noqa: PLC0415

    await AlbumStore(hass, entry.entry_id).async_remove()


# --- services ---------------------------------------------------------------


def _coordinator_for(hass: HomeAssistant, call: ServiceCall) -> AlbumCoordinator:
    entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="unknown_album"
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="album_not_loaded"
        )
    coordinator: AlbumCoordinator = entry.runtime_data
    return coordinator


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_SYNC_NOW):
        return

    async def sync_now(call: ServiceCall) -> None:
        coordinator = _coordinator_for(hass, call)
        if coordinator.syncing:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="already_syncing"
            )
        coordinator.config_entry.async_create_background_task(
            hass,
            coordinator.async_sync(verify=bool(call.data.get(ATTR_FULL))),
            f"{DOMAIN} sync {coordinator.config_entry.entry_id}",
        )

    async def rebuild_index(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator_for(hass, call)
        if coordinator.syncing:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="already_syncing"
            )
        forgotten = await coordinator.syncer.async_rebuild_index()
        coordinator.async_publish()
        await async_write_catalog(hass)
        return {"forgotten": forgotten, "items": len(coordinator.store.state.assets)}

    async def purge_quarantine(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator_for(hass, call)
        days = int(call.data.get(ATTR_OLDER_THAN_DAYS, 0))
        ids = coordinator.syncer.quarantine_older_than(days)
        deleted = await coordinator.syncer.async_delete_quarantined(ids)
        coordinator.async_publish()
        return {"deleted": deleted}

    entry_schema: dict[Any, Any] = {probatio.Required(ATTR_CONFIG_ENTRY_ID): cv.string}
    hass.services.async_register(
        DOMAIN,
        SERVICE_SYNC_NOW,
        sync_now,
        schema=probatio.Schema(
            {**entry_schema, probatio.Optional(ATTR_FULL, default=False): cv.boolean}
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REBUILD_INDEX,
        rebuild_index,
        schema=probatio.Schema(entry_schema),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PURGE_QUARANTINE,
        purge_quarantine,
        schema=probatio.Schema(
            {
                **entry_schema,
                probatio.Optional(ATTR_OLDER_THAN_DAYS, default=0): probatio.All(
                    probatio.Coerce(int), probatio.Range(min=0, max=3650)
                ),
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
