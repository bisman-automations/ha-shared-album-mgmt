"""Admin-only sidebar panel.

The Lit element is built into ``frontend/shared-album-mgmt-panel.js`` (source
in ``frontend/`` at the repo root; ``npm run build`` refreshes it) and served
from this integration. The panel needs an admin because it changes settings
and deletes quarantined files.
"""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import (
    async_register_built_in_panel,
    async_remove_panel,
)
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback

from .const import (
    DOMAIN,
    PANEL_ELEMENT,
    PANEL_ICON,
    PANEL_JS_URL,
    PANEL_TITLE,
    PANEL_URL,
)

_JS = Path(__file__).parent / "frontend" / "shared-album-mgmt-panel.js"


def _version() -> str:
    """Cache-busting query: the integration version from the manifest."""
    import json  # noqa: PLC0415

    manifest = Path(__file__).parent / "manifest.json"
    return str(json.loads(manifest.read_text(encoding="utf-8")).get("version", "0"))


async def async_register_static(hass: HomeAssistant) -> None:
    """Serve the panel script once per Home Assistant run."""
    data = hass.data[DOMAIN]
    if data.get("static"):
        return
    data["version"] = await hass.async_add_executor_job(_version)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(PANEL_JS_URL, str(_JS), True)]
    )
    data["static"] = True


async def async_register_panel(hass: HomeAssistant) -> None:
    """Add (or refresh) the sidebar entry."""
    version = hass.data[DOMAIN].get("version", "0")
    async_register_built_in_panel(
        hass,
        "custom",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        frontend_url_path=PANEL_URL,
        require_admin=True,
        update=True,
        config={
            "_panel_custom": {
                "name": PANEL_ELEMENT,
                "embed_iframe": False,
                "trust_external": False,
                "js_url": f"{PANEL_JS_URL}?v={version}",
            }
        },
    )


@callback
def async_unregister_panel(hass: HomeAssistant) -> None:
    """Remove the sidebar entry. The script route can stay."""
    async_remove_panel(hass, PANEL_URL, warn_if_unknown=False)
