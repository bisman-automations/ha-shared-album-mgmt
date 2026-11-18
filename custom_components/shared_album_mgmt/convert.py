"""HEIC/HEIF to JPEG conversion with pillow-heif.

Runs only in the executor (decoding a 12 MP HEIC takes a few hundred
milliseconds). pillow-heif ships wheels for every platform Home Assistant
supports on Python 3.14, including musllinux aarch64 and x86_64 used by Home
Assistant OS and the container image. If the import still fails (an
unusual platform, a broken wheel), :func:`heic_available` returns False:
the sync engine then saves Apple's largest JPEG instead, or the original
HEIC when there is no JPEG, and raises a Repairs issue that says so.
"""

from __future__ import annotations

from functools import cache
import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)


@cache
def heic_available() -> bool:
    """Import pillow-heif once and register its Pillow opener."""
    try:
        import pillow_heif  # noqa: PLC0415 - optional at runtime on purpose

        pillow_heif.register_heif_opener()
    except Exception:  # noqa: BLE001 - any import failure means "not available"
        _LOGGER.warning(
            "pillow-heif could not be loaded; HEIC photos will be saved as "
            "Apple's JPEG or as HEIC",
            exc_info=True,
        )
        return False
    return True


def convert_heic_to_jpeg(source: Path, target: Path, quality: int) -> None:
    """Decode ``source`` (HEIC/HEIF) and write a JPEG to ``target``.

    The orientation is applied to the pixels so every viewer shows the photo
    the right way up, and the EXIF block (capture date, camera, location) is
    kept with its orientation reset. The colour profile is kept when there
    is one. Blocking: call from the executor.
    """
    if not heic_available():
        raise RuntimeError("pillow-heif is not available")
    from PIL import Image, ImageOps  # noqa: PLC0415 - Pillow ships with HA

    with Image.open(source) as image:
        exif = image.getexif()
        icc = image.info.get("icc_profile")
        upright = ImageOps.exif_transpose(image)
        if upright.mode not in ("RGB", "L"):
            upright = upright.convert("RGB")
        if exif:
            exif[0x0112] = 1  # orientation: already applied
        options: dict[str, object] = {
            "quality": quality,
            "optimize": True,
            "subsampling": "4:2:0" if quality < 95 else "4:4:4",
        }
        if exif:
            options["exif"] = exif.tobytes()
        if icc:
            options["icc_profile"] = icc
        upright.save(target, "JPEG", **options)


def make_thumbnail(source: Path, target: Path, size: int) -> bool:
    """Write a small JPEG preview for the sidebar panel. Blocking.

    Returns False when the file can't be decoded (a video, or HEIC without
    pillow-heif); the panel then shows an icon instead.
    """
    from PIL import Image, ImageOps, UnidentifiedImageError  # noqa: PLC0415

    if source.suffix.lower() in (".heic", ".heif"):
        heic_available()
    try:
        with Image.open(source) as image:
            image.draft("RGB", (size * 2, size * 2))
            thumb = ImageOps.exif_transpose(image)
            thumb.thumbnail((size, size))
            if thumb.mode not in ("RGB", "L"):
                thumb = thumb.convert("RGB")
            target.parent.mkdir(parents=True, exist_ok=True)
            thumb.save(target, "JPEG", quality=80)
    except OSError, UnidentifiedImageError, ValueError:
        return False
    return True
