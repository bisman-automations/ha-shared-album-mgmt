"""Repairs: trust a new Apple host from the issue itself.

When Apple starts using a host that isn't on the allow-list (as it did
with the numbered ``pNN-ckdatabasews`` hosts), the sync stops and raises a fixable
issue naming the host. Confirming adds it to the album's extra trusted
hosts, the album reloads, and the next sync goes through.
"""

from __future__ import annotations

from typing import Any

import probatio

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.core import HomeAssistant

from .const import CONF_EXTRA_HOSTS
from .hosts import normalize_extra_host


class TrustHostRepairFlow(RepairsFlow):
    """Confirm and add the host."""

    def __init__(self, entry_id: str, host: str) -> None:
        """Remember which album and which host."""
        self._entry_id = entry_id
        self._host = host

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Go straight to the confirmation."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Add the host to the album's options."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return self.async_abort(reason="album_removed")
        if user_input is not None:
            host = normalize_extra_host(self._host)
            if host is None:
                return self.async_abort(reason="invalid_host")
            hosts = list(entry.options.get(CONF_EXTRA_HOSTS) or [])
            if host not in hosts:
                hosts.append(host)
            self.hass.config_entries.async_update_entry(
                entry, options={**entry.options, CONF_EXTRA_HOSTS: hosts}
            )
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="confirm",
            data_schema=probatio.Schema({}),
            description_placeholders={"host": self._host, "album": entry.title},
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> RepairsFlow:
    """Create the flow for a fixable issue."""
    if data and "entry_id" in data and "host" in data:
        return TrustHostRepairFlow(str(data["entry_id"]), str(data["host"]))
    return ConfirmRepairFlow()
