"""Thumbnails and full-size files for the sidebar panel.

``GET /api/shared_album_mgmt/media/{entry_id}/{kind}/{key}?size=thumb|full``

- ``kind`` is ``asset`` (key: Apple GUID) or ``quarantine`` (key: quarantine
  id). Only files recorded in the album's store can be served, so the view
  can't be used to read anything else on disk.
- Requests are authenticated. The panel asks the websocket API for signed
  URLs (``async_sign_path``), so ``<img>`` tags work without a header.
- Thumbnails are made once with Pillow in the executor and cached under
  ``.cache/shared_album_mgmt/<entry_id>/``, named by the file's hash so a
  replaced file gets a new thumbnail.
"""

from __future__ import annotations

from http import HTTPStatus
import mimetypes
from pathlib import Path

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, THUMB_SIZE
from .convert import make_thumbnail

MEDIA_URL = f"/api/{DOMAIN}/media"


@callback
def async_register_views(hass: HomeAssistant) -> None:
    """Register the view once."""
    if hass.data[DOMAIN].get("views"):
        return
    hass.http.register_view(AlbumMediaView(hass))
    hass.data[DOMAIN]["views"] = True


def media_path(entry_id: str, kind: str, key: str, size: str = "thumb") -> str:
    """Path of one item (the websocket API signs it)."""
    return f"{MEDIA_URL}/{entry_id}/{kind}/{key}?size={size}"


class AlbumMediaView(HomeAssistantView):
    """Serve stored album files and their thumbnails."""

    url = MEDIA_URL + "/{entry_id}/{kind}/{key}"
    name = f"api:{DOMAIN}:media"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Keep a reference to Home Assistant."""
        self.hass = hass

    async def get(
        self, request: web.Request, entry_id: str, kind: str, key: str
    ) -> web.StreamResponse:
        """Return the thumbnail or the file."""
        user = request.get("hass_user")
        if user is None or not user.is_admin:
            return web.Response(status=HTTPStatus.UNAUTHORIZED)
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if (
            entry is None
            or entry.domain != DOMAIN
            or entry.state is not ConfigEntryState.LOADED
        ):
            return web.Response(status=HTTPStatus.NOT_FOUND)
        coordinator = entry.runtime_data
        state = coordinator.store.state
        if kind == "asset" and key in state.assets:
            record = state.assets[key]
            relative, digest = record.file, record.sha256
        elif kind == "quarantine" and key in state.quarantine:
            qrecord = state.quarantine[key]
            relative, digest = qrecord.stored, qrecord.sha256
        else:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        source: Path = coordinator.target / relative
        if request.query.get("size") == "full":
            if not await self.hass.async_add_executor_job(source.is_file):
                return web.Response(status=HTTPStatus.NOT_FOUND)
            content_type = (
                mimetypes.guess_type(source.name)[0] or "application/octet-stream"
            )
            return web.FileResponse(source, headers={"Content-Type": content_type})
        thumb = Path(
            self.hass.config.cache_path(
                DOMAIN, entry_id, f"{kind}_{key}_{digest[:12]}.jpg"
            )
        )
        if not await self.hass.async_add_executor_job(thumb.is_file):
            made = await self.hass.async_add_executor_job(
                make_thumbnail, source, thumb, THUMB_SIZE
            )
            if not made:
                return web.Response(status=HTTPStatus.NO_CONTENT)
        return web.FileResponse(
            thumb,
            headers={
                "Content-Type": "image/jpeg",
                "Cache-Control": "private, max-age=86400",
            },
        )
