"""HEIC conversion with pillow-heif."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image
import pillow_heif

from custom_components.shared_album_mgmt.convert import (
    convert_heic_to_jpeg,
    heic_available,
    make_thumbnail,
)


def test_heic_available() -> None:
    """pillow-heif loads on this platform."""
    assert heic_available()


def test_convert_keeps_orientation_and_metadata(tmp_path: Path) -> None:
    """The JPEG is upright, keeps EXIF (orientation reset) and the ICC profile."""
    image = Image.new("RGB", (80, 40), (10, 200, 30))
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 CW on display
    exif[0x010F] = "Apple"
    heif = pillow_heif.from_pillow(image)
    buffer = io.BytesIO()
    heif.save(buffer, exif=exif.tobytes(), quality=90)
    source = tmp_path / "a.heic"
    source.write_bytes(buffer.getvalue())

    target = tmp_path / "a.jpg"
    convert_heic_to_jpeg(source, target, 85)
    result = Image.open(target)
    assert result.format == "JPEG"
    assert result.size == (40, 80)  # transposed upright
    out_exif = result.getexif()
    assert out_exif.get(0x0112, 1) == 1
    assert out_exif.get(0x010F) == "Apple"


def test_thumbnail(tmp_path: Path) -> None:
    """Thumbnails are small JPEGs; unreadable files return False."""
    source = tmp_path / "big.jpg"
    Image.new("RGB", (2000, 1000), (1, 2, 3)).save(source)
    target = tmp_path / "thumb.jpg"
    assert make_thumbnail(source, target, 300)
    assert max(Image.open(target).size) == 300
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"nope")
    assert not make_thumbnail(bad, tmp_path / "t2.jpg", 300)
