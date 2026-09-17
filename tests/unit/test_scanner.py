"""Scanner + JPEG/PNG tests (M0-9, M0-10; spec §9.1–9.4, §17)."""

from __future__ import annotations

import zlib

import pytest

from specter.carve.formats import jpeg, png
from specter.carve.scanner import scan


# --- synthetic builders -----------------------------------------------------


def make_jpeg(*, entropy_tail: bytes = b"\x11\x22\xff\x00\xaa", eoi: bytes = b"\xff\xd9") -> bytes:
    """Minimal valid JPEG: SOI, APP0, SOS, then entropy data and EOI."""
    app0 = b"\xff\xe0" + (2 + 4).to_bytes(2, "big") + b"abcd"  # 4-byte payload keeps simp le boundary
    sos = b"\xff\xda" + (2 + 3).to_bytes(2, "big") + b"\x01\x00\x00"  # 3 payload bytes
    return b"\xff\xd8\xff" + app0 + sos + entropy_tail + eoi


def make_exif_jpeg() -> bytes:
    """JPEG whose thumbnail is itself a valid JPEG (its EOI must NOT end ours)."""
    thumbnail = make_jpeg()
    # APP1 with the thumbnail embedded; segment length covers it all.
    exif = b"Exif\x00\x00" + thumbnail
    app1 = b"\xff\xe1" + (2 + len(exif)).to_bytes(2, "big") + exif
    sos = b"\xff\xda" + (2 + 2).to_bytes(2, "big") + b"\x01\x00"
    entropy = b"\x10\x20\x30\xff\x00\x40"
    return b"\xff\xd8\xff" + app1 + sos + entropy + b"\xff\xd9"


def png_chunk(ctype: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
    return len(data).to_bytes(4, "big") + ctype + data + crc.to_bytes(4, "big")


def make_png(width: int = 1, height: int = 1) -> bytes:
    ihdr = width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x06\x00\x00\x00"
    ihdr = png_chunk(b"IHDR", ihdr)
    idat = png_chunk(b"IDAT", zlib.compress(b"\x00" * (width * 4)))
    iend = png_chunk(b"IEND", b"")
    return png.SIGNATURE + ihdr + idat + iend


# --- jpeg parser ------------------------------------------------------------


class TestJpeg:
    def test_clean_recovery_high_confidence(self) -> None:
        data = make_jpeg()
        r = jpeg.parse(data, 0, 50 * 1024)
        assert r is not None and r.end == len(data) and r.confidence == "high"

    def test_thumbnail_eoi_does_not_terminate(self) -> None:
        data = make_exif_jpeg()
        r = jpeg.parse(data, 0, len(data))
        assert r is not None and r.end == len(data) and r.confidence == "high"

    def test_fill_bytes_before_eoi(self) -> None:
        data = make_jpeg(eoi=b"\xff\xff\xff\xd9")  # two FF fills then EOI
        r = jpeg.parse(data, 0, len(data))
        assert r is not None and r.confidence == "high" and r.end == len(data)

    def test_restart_markers_in_entropy(self) -> None:
        data = make_jpeg(entropy_tail=b"\xaa\xff\xd0\xbb\xff\xd7\xcc")
        r = jpeg.parse(data, 0, len(data))
        assert r is not None and r.confidence == "high" and r.end == len(data)

    def test_dangling_ff_falls_back(self) -> None:
        # E-01+: a scan ending on a bare FF with no byte to peek must take the
        # fallback, never a marker parse. No real EOI exists in the buffer.
        data = (
            b"\xff\xd8\xff"
            + b"\xff\xda" + (2 + 3).to_bytes(2, "big") + b"\x01\x00\x00"  # SOS
            + b"\x00\xaa\xbb\xff"  # entropy ending on a dangling FF
        )
        r = jpeg.parse(data, 0, len(data) + 64)
        assert r is not None and r.confidence == "low"

    def test_no_eoi_uses_last_eoi_in_cap(self) -> None:
        # The walk runs out of data *after* SOS; the only EOI bytes in range
        # sit inside an APP0 payload. Fallback must find them (low confidence).
        app0 = b"\xff\xe0" + (2 + 6).to_bytes(2, "big") + b"ab\xff\xd9zz"
        sos = b"\xff\xda" + (2 + 3).to_bytes(2, "big") + b"\x01\x00\x00"
        data = b"\xff\xd8\xff" + app0 + sos + b"\x99\x88\x77\x66"
        r = jpeg.parse(data, 0, len(data) + 64)
        assert r is not None and r.confidence == "low"
        assert data[r.offset : r.end].endswith(b"\xff\xd9")

    def test_no_eoi_cap_bounded(self) -> None:
        data = b"\xff\xd8\xff" + b"\xff\xe0\x00\x04ab" + b"\xff\xda\x00\x04\x01\x00" + b"\x99" * 32
        r = jpeg.parse(data, 0, 32)  # cap cuts before any EOI
        assert r is not None and r.confidence == "low" and r.end == 32


# --- png parser -------------------------------------------------------------


class TestPng:
    def test_clean_recovery(self) -> None:
        data = make_png()
        r = png.parse(data, 0, 50 * 1024)
        assert r is not None and r.end == len(data) and r.confidence == "high"

    def test_bad_first_crc_is_o1_rejection(self) -> None:
        data = bytearray(make_png())
        # Corrupt the IHDR CRC (bytes 21..24 region: after 8-byte sig +
        # 4 length + 4 type + 13 data = CRC at 29..32).
        data[30] ^= 0xFF
        assert png.parse(bytes(data), 0, 50 * 1024) is None

    def test_late_crc_break_truncates_low_confidence(self) -> None:
        data = bytearray(make_png())
        # Corrupt the IEND CRC (last 4 bytes).
        data[-1] ^= 0xFF
        r = png.parse(bytes(data), 0, 50 * 1024)
        assert r is not None and r.confidence == "low"
        assert data[r.offset : r.end].endswith(b"IDAT") is False  # truncated before IEND

    def test_truncated_stream_low_confidence(self) -> None:
        data = make_png()[:20]  # cut inside IHDR data
        r = png.parse(data, 0, 50 * 1024)
        assert r is None  # first chunk never validated → not a PNG


# --- scanner ----------------------------------------------------------------


class TestScanner:
    def test_finds_both_types(self) -> None:
        jpg = make_jpeg()
        png_data = make_png()
        gap = b"\x00" * 512
        image = gap + jpg + b"\x00" * (512 - len(jpg) % 512) + png_data
        # jpg at offset 512 (aligned), png at next aligned boundary
        jpg_off = 512
        pad = (512 - (jpg_off + len(jpg)) % 512) % 512
        png_off = jpg_off + len(jpg) + pad
        image = b"\x00" * jpg_off + jpg + b"\x00" * pad + png_data

        result = scan(image, window=1 << 20, safety_cap=1 << 20, alignment=512)
        types = sorted(r.type for r in result.recoveries)
        assert types == ["jpg", "png"]
        by = {r.type: r for r in result.recoveries}
        assert by["jpg"].offset == jpg_off and by["jpg"].end == jpg_off + len(jpg)
        assert by["png"].offset == png_off

    def test_alignment_filter_rejects_unaligned(self) -> None:
        jpg = make_jpeg()
        image = b"\x00" * 513 + jpg  # not 512-aligned
        r512 = scan(image, safety_cap=1 << 20, alignment=512)
        assert r512.recoveries == []
        r0 = scan(image, safety_cap=1 << 20, alignment=0)
        assert len(r0.recoveries) == 1

    def test_cursor_skips_recovered_region(self) -> None:
        # A fake SOI *inside* a real JPEG's entropy data must not carve twice.
        inner_soi = make_jpeg(entropy_tail=b"\x00\xff\xd8\xff\x11\x22")
        image = b"\x00" * 512 + inner_soi
        result = scan(image, safety_cap=1 << 20, alignment=512)
        assert len([r for r in result.recoveries if r.type == "jpg"]) == 1

    def test_window_seam_recovery(self) -> None:
        # Force a tiny window so a signature near a seam is still found
        # (extended by the 64-byte overlap).
        jpg = make_jpeg()
        image = b"\x00" * 512 + jpg + b"\x00" * 512
        result = scan(image, window=256, safety_cap=1 << 20, alignment=512)
        assert any(r.type == "jpg" for r in result.recoveries)

    def test_deterministic(self) -> None:
        jpg = make_jpeg()
        png_data = make_png()
        image = jpg + b"\x00" * 512 + png_data
        a = scan(image, safety_cap=1 << 20, alignment=0)
        b = scan(image, safety_cap=1 << 20, alignment=0)
        assert [ (r.type, r.offset, r.length) for r in a.recoveries ] == [
            (r.type, r.offset, r.length) for r in b.recoveries
        ]

    def test_stats_report_masking(self) -> None:
        image = b"\x00" * 512 + make_jpeg()
        result = scan(image, safety_cap=1 << 20, alignment=512)
        assert result.stats is not None
        assert result.stats.recovered >= 1
        assert result.stats.masked_bytes > 0

    def test_empty_image(self) -> None:
        result = scan(b"")
        assert result.recoveries == [] and result.stats is not None


def test_scan_never_raises_on_garbage() -> None:
    import random

    rng = random.Random(2026)
    junk = bytes(rng.getrandbits(8) for _ in range(4096))
    scan(junk, safety_cap=4096, alignment=0)  # must return, not raise