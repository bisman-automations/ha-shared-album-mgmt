"""Config flow for Shared Album Mgmt.

One config entry per public shared album. The user step reads the album
once to prove the link works (and to suggest a name), the settings step
picks the folder and the main choices, and the options flow edits every
setting in sections. The sidebar panel adds albums through the ``panel``
step, which runs the same checks without a form.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

import probatio

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import AlbumListing, SharedAlbumClient, describe_error
from .const import (
    CONF_ALBUM_ID,
    CONF_CONCURRENCY,
    CONF_EXTRA_HOSTS,
    CONF_FOLDER,
    CONF_INTERVAL,
    CONF_JPEG_QUALITY,
    CONF_KEEP_DAYS,
    CONF_KIND,
    CONF_LEAVE_MODE,
    CONF_MAX_FILES,
    CONF_MEDIA_DIR,
    CONF_MIN_FREE_MB,
    CONF_MIN_LONG_EDGE,
    CONF_MIN_SIZE_KB,
    CONF_NAME,
    CONF_PHOTO_FORMAT,
    CONF_SYNC_PHOTOS,
    CONF_SYNC_VIDEOS,
    CONF_URL,
    CONF_WRITE_INDEX,
    CONF_WRITE_LATEST,
    DOMAIN,
    MAX_CONCURRENCY,
    MAX_INTERVAL,
    SECTION_ADVANCED,
    SECTION_CONTENT,
    SECTION_LIMITS,
    SECTION_SCHEDULE,
    SECTION_STORAGE,
    LeaveMode,
    PhotoFormat,
)
from .exceptions import SharedAlbumError
from .hosts import normalize_extra_host
from .links import AlbumLink, parse_link
from .options import async_validate_options, default_options, folder_for, with_defaults


async def async_probe(
    hass: HomeAssistant, link: AlbumLink, extra_hosts: tuple[str, ...] = ()
) -> AlbumListing:
    """Read the album once. Raises the same errors a sync would."""
    client = SharedAlbumClient(
        async_get_clientsession(hass), link, extra_hosts=extra_hosts
    )
    return await client.async_list()


def _entry_data(link: AlbumLink) -> dict[str, Any]:
    return {
        CONF_URL: link.url,
        CONF_KIND: link.kind.value,
        CONF_ALBUM_ID: link.album_id,
        "china": link.china,
    }


def _select(options: list[str], key: str, *, dropdown: bool = False) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            translation_key=key,
            mode=SelectSelectorMode.DROPDOWN if dropdown else SelectSelectorMode.LIST,
        )
    )


def _number(
    low: int, high: int, unit: str | None = None, step: int = 1
) -> NumberSelector:
    config = NumberSelectorConfig(
        min=low, max=high, step=step, mode=NumberSelectorMode.BOX
    )
    if unit:
        config["unit_of_measurement"] = unit
    return NumberSelector(config)


def _media_dir_selector(hass: HomeAssistant) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=sorted(hass.config.media_dirs) or ["local"],
            mode=SelectSelectorMode.DROPDOWN,
            custom_value=False,
        )
    )


def _flatten(user_input: Mapping[str, Any]) -> dict[str, Any]:
    """Options-flow sections arrive nested; options are stored flat."""
    flat: dict[str, Any] = {}
    for key, value in user_input.items():
        if isinstance(value, Mapping):
            flat.update(value)
        else:
            flat[key] = value
    return flat


def _error_for_field(errors: dict[str, str]) -> dict[str, str]:
    """Map flat option errors onto their section for the form."""
    where = {
        CONF_INTERVAL: SECTION_SCHEDULE,
        CONF_SYNC_PHOTOS: SECTION_CONTENT,
        CONF_PHOTO_FORMAT: SECTION_CONTENT,
        CONF_LEAVE_MODE: SECTION_CONTENT,
        CONF_MEDIA_DIR: SECTION_STORAGE,
        CONF_FOLDER: SECTION_STORAGE,
    }
    return {
        where.get(k, SECTION_LIMITS if k in _LIMIT_KEYS else SECTION_ADVANCED): v
        for k, v in errors.items()
    }


def _clean_hosts(raw: Any) -> list[str] | None:
    """Extra trusted hosts from a form, or None when one isn't a host name."""
    if not raw:
        return []
    items = re.split(r"[\s,]+", raw) if isinstance(raw, str) else list(raw)
    hosts: list[str] = []
    for item in items:
        if not str(item).strip():
            continue
        host = normalize_extra_host(str(item))
        if host is None:
            return None
        if host not in hosts:
            hosts.append(host)
    return hosts


_LIMIT_KEYS = {CONF_KEEP_DAYS, CONF_MAX_FILES, CONF_MIN_SIZE_KB, CONF_MIN_LONG_EDGE}


class SharedAlbumConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a public shared album."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Start empty."""
        self._link: AlbumLink | None = None
        self._listing: AlbumListing | None = None
        self._title = ""
        self._extra_hosts: list[str] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SharedAlbumOptionsFlow:
        """Edit an album's settings."""
        return SharedAlbumOptionsFlow()

    async def _check(
        self, url: str, hosts: Any = None
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Parse and read the album. Returns errors and placeholders."""
        cleaned = _clean_hosts(hosts)
        if cleaned is None:
            return {"base": "invalid_host"}, {}
        self._extra_hosts = cleaned
        try:
            self._link = parse_link(url)
            self._listing = await async_probe(
                self.hass, self._link, tuple(self._extra_hosts)
            )
        except SharedAlbumError as err:
            key, placeholders = describe_error(err)
            return {"base": key}, placeholders
        return {}, {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Paste the album's public link."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            user_input = _flatten(user_input)
            errors, placeholders = await self._check(
                user_input[CONF_URL], user_input.get(CONF_EXTRA_HOSTS)
            )
            if not errors and self._link is not None and self._listing is not None:
                await self.async_set_unique_id(self._link.unique_id)
                self._abort_if_unique_id_configured()
                self._title = (
                    (user_input.get(CONF_NAME) or "").strip()
                    or self._listing.name
                    or "Shared album"
                )
                return await self.async_step_settings()
        schema = probatio.Schema(
            {
                probatio.Required(
                    CONF_URL, default=(user_input or {}).get(CONF_URL, "")
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
                probatio.Optional(CONF_NAME): TextSelector(),
                probatio.Required(SECTION_ADVANCED): section(
                    probatio.Schema(
                        {
                            probatio.Optional(
                                CONF_EXTRA_HOSTS, default=self._extra_hosts
                            ): TextSelector(TextSelectorConfig(multiple=True)),
                        }
                    ),
                    {"collapsed": errors.get("base") != "untrusted_host"},
                ),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the folder, the Photo format and what happens on removal."""
        assert self._link is not None and self._listing is not None
        defaults = {
            **default_options(self.hass, self._title),
            CONF_EXTRA_HOSTS: self._extra_hosts,
        }
        errors: dict[str, str] = {}
        if user_input is not None:
            cleaned, field_errors = await async_validate_options(
                self.hass, user_input, defaults
            )
            errors = field_errors
            if not errors:
                return self.async_create_entry(
                    title=self._title, data=_entry_data(self._link), options=cleaned
                )
        photos = sum(1 for i in self._listing.items if not i.is_video)
        schema = probatio.Schema(
            {
                probatio.Required(
                    CONF_MEDIA_DIR, default=defaults[CONF_MEDIA_DIR]
                ): _media_dir_selector(self.hass),
                probatio.Required(
                    CONF_FOLDER, default=defaults[CONF_FOLDER]
                ): TextSelector(),
                probatio.Required(
                    CONF_PHOTO_FORMAT, default=defaults[CONF_PHOTO_FORMAT]
                ): _select([f.value for f in PhotoFormat], CONF_PHOTO_FORMAT),
                probatio.Required(
                    CONF_LEAVE_MODE, default=defaults[CONF_LEAVE_MODE]
                ): _select([m.value for m in LeaveMode], CONF_LEAVE_MODE),
                probatio.Required(
                    CONF_INTERVAL, default=defaults[CONF_INTERVAL]
                ): _number(0, MAX_INTERVAL, "min", 5),
            }
        )
        if user_input:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(
            step_id="settings",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "album": self._title,
                "photos": str(photos),
                "videos": str(len(self._listing.items) - photos),
            },
        )

    async def async_step_panel(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Add an album from the sidebar panel (no form)."""
        errors, placeholders = await self._check(
            str(data.get(CONF_URL, "")), data.get(CONF_EXTRA_HOSTS)
        )
        if errors or self._link is None or self._listing is None:
            return self.async_abort(
                reason=errors.get("base", "unknown"),
                description_placeholders=placeholders,
            )
        await self.async_set_unique_id(self._link.unique_id)
        self._abort_if_unique_id_configured()
        title = (
            (data.get(CONF_NAME) or "").strip() or self._listing.name or "Shared album"
        )
        defaults = {
            **default_options(self.hass, title),
            CONF_EXTRA_HOSTS: self._extra_hosts,
        }
        overrides = {k: data[k] for k in (CONF_MEDIA_DIR, CONF_FOLDER) if data.get(k)}
        cleaned, field_errors = await async_validate_options(
            self.hass, overrides, defaults
        )
        if field_errors:
            return self.async_abort(reason=next(iter(field_errors.values())))
        return self.async_create_entry(
            title=title, data=_entry_data(self._link), options=cleaned
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the link or the name. A different album must not exist yet."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            errors, placeholders = await self._check(
                user_input[CONF_URL], entry.options.get(CONF_EXTRA_HOSTS)
            )
            if not errors and self._link is not None:
                await self.async_set_unique_id(self._link.unique_id)
                if self._link.unique_id != entry.unique_id:
                    self._abort_if_unique_id_configured()
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=self._link.unique_id,
                    title=(user_input.get(CONF_NAME) or "").strip() or entry.title,
                    data=_entry_data(self._link),
                )
        schema = probatio.Schema(
            {
                probatio.Required(CONF_URL, default=entry.data[CONF_URL]): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
                probatio.Optional(CONF_NAME, default=entry.title): TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )


class SharedAlbumOptionsFlow(OptionsFlow):
    """Every album setting, grouped in sections."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and save the settings. The album reloads after saving."""
        entry = self.config_entry
        current = with_defaults(self.hass, entry.title, entry.options)
        errors: dict[str, str] = {}
        if user_input is not None:
            cleaned, field_errors = await async_validate_options(
                self.hass, _flatten(user_input), current
            )
            if not field_errors:
                return self.async_create_entry(data=cleaned)
            errors = _error_for_field(field_errors)
            current = {**current, **_flatten(user_input)}
        hosts = current.get(CONF_EXTRA_HOSTS) or []
        schema = probatio.Schema(
            {
                probatio.Required(SECTION_SCHEDULE): section(
                    probatio.Schema(
                        {
                            probatio.Required(
                                CONF_INTERVAL, default=current[CONF_INTERVAL]
                            ): _number(0, MAX_INTERVAL, "min", 5),
                        }
                    ),
                    {"collapsed": False},
                ),
                probatio.Required(SECTION_CONTENT): section(
                    probatio.Schema(
                        {
                            probatio.Required(
                                CONF_SYNC_PHOTOS, default=current[CONF_SYNC_PHOTOS]
                            ): BooleanSelector(),
                            probatio.Required(
                                CONF_SYNC_VIDEOS, default=current[CONF_SYNC_VIDEOS]
                            ): BooleanSelector(),
                            probatio.Required(
                                CONF_PHOTO_FORMAT, default=current[CONF_PHOTO_FORMAT]
                            ): _select(
                                [f.value for f in PhotoFormat], CONF_PHOTO_FORMAT
                            ),
                            probatio.Required(
                                CONF_LEAVE_MODE, default=current[CONF_LEAVE_MODE]
                            ): _select([m.value for m in LeaveMode], CONF_LEAVE_MODE),
                        }
                    ),
                    {"collapsed": False},
                ),
                probatio.Required(SECTION_STORAGE): section(
                    probatio.Schema(
                        {
                            probatio.Required(
                                CONF_MEDIA_DIR, default=current[CONF_MEDIA_DIR]
                            ): _media_dir_selector(self.hass),
                            probatio.Required(
                                CONF_FOLDER,
                                default=current[CONF_FOLDER] or folder_for(entry.title),
                            ): TextSelector(),
                            probatio.Required(
                                CONF_WRITE_LATEST, default=current[CONF_WRITE_LATEST]
                            ): BooleanSelector(),
                            probatio.Required(
                                CONF_WRITE_INDEX, default=current[CONF_WRITE_INDEX]
                            ): BooleanSelector(),
                        }
                    ),
                    {"collapsed": False},
                ),
                probatio.Required(SECTION_LIMITS): section(
                    probatio.Schema(
                        {
                            probatio.Required(
                                CONF_KEEP_DAYS, default=current[CONF_KEEP_DAYS]
                            ): _number(0, 36500, "d"),
                            probatio.Required(
                                CONF_MAX_FILES, default=current[CONF_MAX_FILES]
                            ): _number(0, 1_000_000),
                            probatio.Required(
                                CONF_MIN_SIZE_KB, default=current[CONF_MIN_SIZE_KB]
                            ): _number(0, 1_000_000, "kB"),
                            probatio.Required(
                                CONF_MIN_LONG_EDGE, default=current[CONF_MIN_LONG_EDGE]
                            ): _number(0, 20000, "px"),
                        }
                    ),
                    {"collapsed": True},
                ),
                probatio.Required(SECTION_ADVANCED): section(
                    probatio.Schema(
                        {
                            probatio.Optional(
                                CONF_EXTRA_HOSTS, default=list(hosts)
                            ): TextSelector(TextSelectorConfig(multiple=True)),
                            probatio.Required(
                                CONF_CONCURRENCY, default=current[CONF_CONCURRENCY]
                            ): _number(1, MAX_CONCURRENCY),
                            probatio.Required(
                                CONF_MIN_FREE_MB, default=current[CONF_MIN_FREE_MB]
                            ): _number(0, 10_000_000, "MB"),
                            probatio.Required(
                                CONF_JPEG_QUALITY, default=current[CONF_JPEG_QUALITY]
                            ): _number(50, 100, "%"),
                        }
                    ),
                    {"collapsed": True},
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
