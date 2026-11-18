"""The sync engine: downloads, formats, leave modes and the safety rules."""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

from PIL import Image
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shared_album_mgmt.const import DOMAIN
from custom_components.shared_album_mgmt.coordinator import AlbumCoordinator
from custom_components.shared_album_mgmt.repairs import async_create_fix_flow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .conftest import LEGACY_URL, MODERN_ID, NOW_MS, make_entry, setup_entry
from .fake_apple import FakeApple

FOLDER = "shared_albums/family_photos"


def coord(entry: MockConfigEntry) -> AlbumCoordinator:
    return entry.runtime_data


def album_dir(media_dir: Path) -> Path:
    return media_dir / FOLDER


def files(folder: Path) -> set[str]:
    return {p.name for p in folder.iterdir() if p.is_file()}


def variant(apple: FakeApple, guid: str, key: str) -> bytes:
    for item in apple.albums[MODERN_ID].items:
        if item.guid == guid:
            return item.variants[key].data
    raise KeyError(guid)


def remove(apple: FakeApple, *guids: str) -> None:
    album = apple.albums[MODERN_ID]
    album.items = [i for i in album.items if i.guid not in guids]


async def test_first_sync_converts_heic(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Default settings: largest version, HEIC converted, index and latest written."""
    entry = await setup_entry(hass, make_entry())
    folder = album_dir(media_dir)
    assert files(folder) == {
        "IMG_0001.jpg",
        "IMG_0002.jpg",
        "IMG_0003.mov",
        "index.json",
        "latest.jpg",
    }
    converted = Image.open(folder / "IMG_0001.jpg")
    assert converted.format == "JPEG"
    assert converted.size == (96, 72)
    assert (folder / "IMG_0002.jpg").read_bytes() == variant(apple, "G2", "Original")
    assert (folder / "IMG_0003.mov").read_bytes() == variant(apple, "G3", "Original")
    assert (folder / "latest.jpg").read_bytes() == (
        folder / "IMG_0001.jpg"
    ).read_bytes()

    index = json.loads((folder / "index.json").read_text())
    assert index["version"] == 2
    assert index["album"] == {"name": "Family Photos", "slug": "family_photos"}
    assert [i["filename"] for i in index["items"]] == [
        "IMG_0001.jpg",
        "IMG_0002.jpg",
        "IMG_0003.mov",
    ]
    first = index["items"][0]
    assert first["media_type"] == "image"
    assert (
        first["media_content_id"]
        == f"media-source://media_source/local/{FOLDER}/IMG_0001.jpg"
    )
    assert first["path"] is None

    catalog = json.loads((media_dir / "shared_albums/albums.json").read_text())
    assert catalog["albums"][0]["name"] == "Family Photos"

    snap = coord(entry).data
    assert snap.item_count == 3
    assert snap.remote_count == 3
    assert snap.last_error is None
    assert snap.last_result["converted"] == 1
    assert snap.last_result["downloaded"] == 3
    assert snap.latest_file == "IMG_0001.jpg"
    assert not list(folder.glob(".*partial"))

    # A second run downloads nothing.
    apple.calls.clear()
    result = await coord(entry).async_sync()
    assert result is not None
    assert result.unchanged == 3
    assert result.downloaded == 0
    assert not [c for c in apple.calls if "icloud-content" in c[1]]


async def test_keep_originals(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Keep originals saves Apple's original bytes, HEIC included."""
    await setup_entry(hass, make_entry(photo_format="original"))
    folder = album_dir(media_dir)
    assert (folder / "IMG_0001.heic").read_bytes() == variant(apple, "G1", "Original")
    # latest.jpg only comes from JPEG/PNG files.
    assert (folder / "latest.jpg").read_bytes() == variant(apple, "G2", "Original")


async def test_dashboard_size(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Apple's smaller JPEG and the medium video."""
    await setup_entry(hass, make_entry(photo_format="dashboard"))
    folder = album_dir(media_dir)
    assert (folder / "IMG_0001.jpg").read_bytes() == variant(apple, "G1", "JPEGMed")
    assert (folder / "IMG_0003.mp4").read_bytes() == variant(apple, "G3", "VidMed")


async def test_dashboard_heic_only_converts(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Dashboard size with only a HEIC original still saves a JPEG.

    Live public albums often carry just the original and a thumbnail.
    """
    album = apple.albums[MODERN_ID]
    first = next(i for i in album.items if i.guid == "G1")
    first.variants = {"Original": first.variants["Original"]}
    entry = await setup_entry(hass, make_entry(photo_format="dashboard"))
    folder = album_dir(media_dir)
    assert Image.open(folder / "IMG_0001.jpg").format == "JPEG"
    assert not (folder / "IMG_0001.heic").exists()
    assert coord(entry).data.last_result["converted"] == 1


async def test_heic_unavailable_falls_back(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Without pillow-heif, Convert uses Apple's JPEG and raises a Repairs note."""
    with (
        patch(
            "custom_components.shared_album_mgmt.sync.heic_available",
            return_value=False,
        ),
        patch(
            "custom_components.shared_album_mgmt.coordinator.heic_available",
            return_value=False,
        ),
    ):
        entry = await setup_entry(hass, make_entry())
    folder = album_dir(media_dir)
    assert (folder / "IMG_0001.jpg").read_bytes() == variant(apple, "G1", "JPEGMed")
    assert coord(entry).data.last_result["heic_fallback"] is True
    assert ir.async_get(hass).async_get_issue(DOMAIN, "heic_unavailable")


async def test_photos_only_and_limits(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Toggles and max files; lowering a limit prunes unchanged copies."""
    entry = await setup_entry(hass, make_entry(sync_videos=False))
    folder = album_dir(media_dir)
    assert "IMG_0003.mov" not in files(folder)
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "max_files": 1}
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert files(folder) == {"IMG_0001.jpg", "index.json", "latest.jpg"}
    assert entry.runtime_data.data.last_result["pruned"] == 1


async def test_keep_days_and_min_edge(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Old photos and small renditions are skipped."""
    apple.albums[MODERN_ID].items.append(
        FakeApple.photo("OLD", "OLD.JPG", 1_000_000_000_000)
    )
    entry = await setup_entry(hass, make_entry(keep_days=3650, min_long_edge=5000))
    assert files(album_dir(media_dir)) == {"index.json"}
    assert coord(entry).data.last_result["skipped"] == 4
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "min_long_edge": 0, "keep_days": 1}
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert "OLD.jpg" not in files(album_dir(media_dir))


async def test_format_change_replaces_file(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Switching to Keep originals swaps the converted JPEG for the HEIC."""
    entry = await setup_entry(hass, make_entry())
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "photo_format": "original"}
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    names = files(album_dir(media_dir))
    assert "IMG_0001.heic" in names
    assert "IMG_0001.jpg" not in names
    assert "IMG_0002.jpg" in names  # already the original


@pytest.mark.parametrize("mode", ["quarantine", "keep", "delete"])
async def test_leave_modes(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path, mode: str
) -> None:
    """A photo that leaves the album is moved aside, kept or deleted."""
    entry = await setup_entry(hass, make_entry(leave_mode=mode))
    folder = album_dir(media_dir)
    g2 = variant(apple, "G2", "Original")
    remove(apple, "G2")
    result = await coord(entry).async_sync()
    assert result is not None
    state = coord(entry).store.state
    if mode == "quarantine":
        assert not (folder / "IMG_0002.jpg").exists()
        assert (folder / ".quarantine/IMG_0002.jpg").read_bytes() == g2
        assert result.quarantined == 1
        assert len(state.quarantine) == 1
        assert "G2" not in state.assets
    elif mode == "keep":
        assert (folder / "IMG_0002.jpg").exists()
        assert result.kept == 1
        assert state.assets["G2"].in_album is False
        # Kept files stay in the index.
        index = json.loads((folder / "index.json").read_text())
        assert {i["filename"]: i["in_album"] for i in index["items"]}[
            "IMG_0002.jpg"
        ] is False
    else:
        assert not (folder / "IMG_0002.jpg").exists()
        assert not (folder / ".quarantine").exists()
        assert result.removed == 1
        assert "G2" not in state.assets


async def test_empty_listing_never_removes(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """An empty answer from Apple is never mirrored."""
    entry = await setup_entry(hass, make_entry(leave_mode="delete"))
    apple.empty = True
    result = await coord(entry).async_sync()
    assert result is not None
    assert "empty_listing" in result.warnings
    assert result.removed == 0
    assert {"IMG_0001.jpg", "IMG_0002.jpg", "IMG_0003.mov"} <= files(
        album_dir(media_dir)
    )


async def test_partial_listing_never_removes(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """A listing that stops part way raises; nothing is touched."""
    entry = await setup_entry(hass, make_entry(leave_mode="delete"))
    apple.page_size = 1
    apple.repeat_marker = True
    assert await coord(entry).async_sync() is None
    assert coord(entry).data.last_error == "incomplete_listing"
    assert {"IMG_0001.jpg", "IMG_0002.jpg", "IMG_0003.mov"} <= files(
        album_dir(media_dir)
    )


async def test_baseline_first(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Until one full listing has been read, nothing counts as removed."""
    entry = await setup_entry(hass, make_entry())
    coord(entry).store.state.baseline = False
    remove(apple, "G2")
    result = await coord(entry).async_sync()
    assert result is not None
    assert result.warnings == ["baseline_pending"]
    assert (album_dir(media_dir) / "IMG_0002.jpg").exists()
    assert coord(entry).store.state.baseline is True
    result = await coord(entry).async_sync()
    assert result is not None
    assert result.quarantined == 1


async def test_mass_removal_needs_two_listings(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Most of the album vanishing is held until the next listing agrees."""
    album = apple.albums[MODERN_ID]
    album.items = [
        FakeApple.photo(f"M{n}", f"M{n:02}.JPG", NOW_MS - n * 1000) for n in range(14)
    ]
    entry = await setup_entry(hass, make_entry())
    album.items = album.items[:2]
    result = await coord(entry).async_sync()
    assert result is not None
    assert result.warnings == ["mass_removal_held"]
    assert len(files(album_dir(media_dir))) == 16
    # A different set the next time resets the hold.
    album.items = [
        FakeApple.photo(f"M{n}", f"M{n:02}.JPG", NOW_MS - n * 1000) for n in (0, 1, 2)
    ]
    result = await coord(entry).async_sync()
    assert result is not None
    assert result.warnings == ["mass_removal_held"]
    result = await coord(entry).async_sync()
    assert result is not None
    assert result.quarantined == 11


async def test_changed_file_is_left_alone(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """A file edited on disk is never moved or deleted."""
    entry = await setup_entry(hass, make_entry(leave_mode="delete"))
    path = album_dir(media_dir) / "IMG_0002.jpg"
    path.write_bytes(b"edited by me")
    remove(apple, "G2")
    result = await coord(entry).async_sync()
    assert result is not None
    assert path.read_bytes() == b"edited by me"
    assert result.removed == 0
    assert "G2" not in coord(entry).store.state.assets


async def test_restore_and_purge(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Restored files are kept for good; purge deletes quarantined files."""
    entry = await setup_entry(hass, make_entry())
    syncer = coord(entry).syncer
    folder = album_dir(media_dir)
    remove(apple, "G2", "G3")
    await coord(entry).async_sync()
    qids = {q.file: qid for qid, q in coord(entry).store.state.quarantine.items()}
    assert set(qids) == {"IMG_0002.jpg", "IMG_0003.mov"}

    name = await syncer.async_restore(qids["IMG_0002.jpg"])
    assert name == "IMG_0002.jpg"
    assert (folder / "IMG_0002.jpg").exists()
    record = coord(entry).store.state.assets["G2"]
    assert record.pinned and not record.in_album
    result = await coord(entry).async_sync()
    assert result is not None
    assert result.quarantined == 0
    assert (folder / "IMG_0002.jpg").exists()

    assert syncer.quarantine_older_than(30) == []
    assert syncer.quarantine_older_than(0) == [qids["IMG_0003.mov"]]
    assert await syncer.async_delete_quarantined([qids["IMG_0003.mov"], "nope"]) == 1
    assert not (folder / ".quarantine/IMG_0003.mov").exists()


async def test_name_clash_in_quarantine_and_folder(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Same names get a counter instead of overwriting."""
    album = apple.albums[MODERN_ID]
    album.items.append(
        FakeApple.photo("G9", "IMG_0002.JPG", NOW_MS - 10 * 86_400_000, color=(1, 2, 3))
    )
    folder = album_dir(media_dir)
    folder.mkdir(parents=True)
    (folder / "IMG_0001.jpg").write_bytes(b"mine")
    await setup_entry(hass, make_entry())
    names = files(folder)
    assert {"IMG_0001.jpg", "IMG_0001_2.jpg", "IMG_0002.jpg", "IMG_0002_2.jpg"} <= names
    assert (folder / "IMG_0001.jpg").read_bytes() == b"mine"


async def test_download_retry_and_failure(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Two failures are retried; three count as failed without stopping others."""
    apple.fail_download_times = {"G1": 2, "G2": 3}
    entry = await setup_entry(hass, make_entry())
    folder = album_dir(media_dir)
    names = files(folder)
    assert "IMG_0001.jpg" in names
    assert "IMG_0002.jpg" not in names
    assert not list(folder.glob(".*partial"))
    snap = coord(entry).data
    assert snap.last_error == "download_failed"
    assert snap.last_error_placeholders == {"count": "1"}
    assert snap.problem
    # Next run picks it up and clears the error.
    await coord(entry).async_sync()
    assert "IMG_0002.jpg" in files(folder)
    assert coord(entry).data.last_error is None


async def test_wrong_size_is_failed(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """A short download isn't kept."""
    apple.wrong_size = True
    entry = await setup_entry(hass, make_entry())
    assert coord(entry).data.last_result["failed"] == 3
    assert files(album_dir(media_dir)) == {"index.json"}


async def test_verify_redownloads_changed_files(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Check every file compares hashes, not just sizes."""
    entry = await setup_entry(hass, make_entry())
    path = album_dir(media_dir) / "IMG_0002.jpg"
    original = path.read_bytes()
    path.write_bytes(bytes(len(original)))
    result = await coord(entry).async_sync()
    assert result is not None and result.downloaded == 0
    result = await coord(entry).async_sync(verify=True)
    assert result is not None and result.downloaded == 1
    assert path.read_bytes() == original


async def test_leftover_partials_removed(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Temp files from an interrupted run are cleaned up."""
    folder = album_dir(media_dir)
    folder.mkdir(parents=True)
    (folder / ".IMG_0001.jpg.partial").write_bytes(b"x")
    await setup_entry(hass, make_entry())
    assert not (folder / ".IMG_0001.jpg.partial").exists()


async def test_low_disk_space(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """The free-space guard stops before downloading and raises an issue."""
    with patch(
        "custom_components.shared_album_mgmt.sync._fs_free_bytes", return_value=1024
    ):
        entry = await setup_entry(hass, make_entry())
    assert coord(entry).data.last_error == "low_disk_space"
    issue_id = f"low_disk_space_{entry.entry_id}"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert files(album_dir(media_dir)) == set()
    await coord(entry).async_sync()
    assert coord(entry).data.last_error is None
    assert not ir.async_get(hass).async_get_issue(DOMAIN, issue_id)


async def test_album_gone_issue(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """An album that disappears keeps its files and raises an issue."""
    entry = await setup_entry(hass, make_entry(leave_mode="delete"))
    del apple.albums[MODERN_ID]
    await coord(entry).async_sync()
    assert coord(entry).data.last_error == "album_not_found"
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"album_gone_{entry.entry_id}")
    assert "IMG_0001.jpg" in files(album_dir(media_dir))


async def test_untrusted_host_issue_and_fix(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """A new, untrusted partition host stops the sync with a fixable issue."""
    apple.albums[MODERN_ID].partition = "https://p99-newhost.icloud.example"
    entry = await setup_entry(hass, make_entry())
    snap = coord(entry).data
    assert snap.last_error == "untrusted_host"
    assert snap.last_error_placeholders == {
        "host": "p99-newhost.icloud.example",
        "kind": "cloudkit",
    }
    issue_id = f"untrusted_host_{entry.entry_id}"
    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert issue is not None and issue.is_fixable
    assert issue.translation_placeholders["host"] == "p99-newhost.icloud.example"

    flow = await async_create_fix_flow(hass, issue_id, issue.data)
    flow.hass = hass
    result = await flow.async_step_init()
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"]["host"] == "p99-newhost.icloud.example"
    result = await flow.async_step_confirm({})
    assert result["type"] == "create_entry"
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.options["extra_trusted_hosts"] == ["p99-newhost.icloud.example"]
    assert coord(entry).data.last_error is None
    assert not ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert "IMG_0001.jpg" in files(album_dir(media_dir))


async def test_fix_flow_for_removed_album(hass: HomeAssistant) -> None:
    """The repair aborts when the album was removed meanwhile."""
    flow = await async_create_fix_flow(
        hass, "x", {"entry_id": "gone", "host": "a.example"}
    )
    flow.hass = hass
    result = await flow.async_step_init()
    assert result["reason"] == "album_removed"


async def test_legacy_album_sync(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Legacy albums sync the same way."""
    entry = await setup_entry(hass, make_entry(LEGACY_URL, "Old Album"))
    names = files(media_dir / "shared_albums/old_album")
    assert any(n.endswith(".jpg") and n.startswith("icloud_") for n in names)
    assert any(n.endswith(".mp4") for n in names)
    assert coord(entry).data.item_count == 2


async def test_rebuild_index(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Records for files deleted by hand are dropped."""
    entry = await setup_entry(hass, make_entry())
    (album_dir(media_dir) / "IMG_0002.jpg").unlink()
    assert await coord(entry).syncer.async_rebuild_index() == 1
    index = json.loads((album_dir(media_dir) / "index.json").read_text())
    assert len(index["items"]) == 2


async def test_concurrent_sync_is_refused(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """Only one sync per album runs at a time."""
    entry = await setup_entry(hass, make_entry())
    async with coord(entry)._lock:
        assert coord(entry).syncing
        assert await coord(entry).async_sync() is None


async def test_folder_problem_is_reported(
    hass: HomeAssistant, apple: FakeApple, media_dir: Path
) -> None:
    """A folder that can't be written shows a storage error."""
    entry = await setup_entry(hass, make_entry())
    with patch(
        "custom_components.shared_album_mgmt.sync._fs_prepare",
        side_effect=PermissionError(13, "Permission denied"),
    ):
        await coord(entry).async_sync()
    assert coord(entry).data.last_error == "storage_error"
    assert coord(entry).data.last_error_placeholders == {"error": "Permission denied"}


def test_jpeg_helper_roundtrip() -> None:
    """Fixture sanity: the fake JPEG decodes."""
    from .fake_apple import jpeg_bytes

    assert Image.open(io.BytesIO(jpeg_bytes())).format == "JPEG"
