"""Unit tests for the mmap accessor (M0-6; spec §6, §9.1, §13, §17)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from specter.carve.mmap_accessor import ImageOpenError, open_image


def test_open_maps_bytes_read_only(tmp_path: Path) -> None:
    payload = b"specter-test-image" * 64  # a little over 1 KiB
    f = tmp_path / "image.dd"
    f.write_bytes(payload)

    with open_image(f) as img:
        assert img.size == len(payload)
        assert img.stat.size == len(payload)
        assert img.stat.inode == os.stat(f).st_ino
        # Slicing is available for zero-copy reads by the scanner.
        assert img.data[8:12] == b"test"


def test_mapping_is_never_writable(tmp_path: Path) -> None:
    f = tmp_path / "image.dd"
    f.write_bytes(b"0123456789abcdef")

    with open_image(f) as img:
        with pytest.raises(TypeError):
            img.data[0:1] = b"Z"  # a write must never succeed (§6)


def test_zero_length_image_refused(tmp_path: Path) -> None:
    f = tmp_path / "empty.dd"
    f.write_bytes(b"")
    with pytest.raises(ImageOpenError, match="Zero-length"):
        open_image(f)


def test_missing_image_refused(tmp_path: Path) -> None:
    with pytest.raises((FileNotFoundError, ImageOpenError)):
        open_image(tmp_path / "nope.dd")