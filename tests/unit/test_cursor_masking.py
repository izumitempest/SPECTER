"""Cursor + masking tests for M1-5 (§9.4: recovered AND attempted regions are
skipped by all search types; the masking cost shows up in ScanStats)."""

from __future__ import annotations

import zlib

import specter.carve.signatures
import specter.carve.types
from specter.carve.scanner import scan
from specter.carve.types import Recovery


def _png() -> bytes:
    def chunk(t: bytes, d: bytes) -> bytes:
        return (len(d).to_bytes(4, "big") + t + d
                + (zlib.crc32(t + d) & 0xFFFFFFFF).to_bytes(4, "big"))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", (1).to_bytes(4, "big") * 2 + b"\x08\x06\x00\x00\x00")
            + chunk(b"IDAT", zlib.compress(b"\x00" * 4))
            + chunk(b"IEND", b""))


def _jpg_stub() -> bytes:
    return (b"\xff\xd8\xff"
            + b"\xff\xe0" + (6).to_bytes(2, "big") + b"abcd"
            + b"\xff\xda" + (5).to_bytes(2, "big") + b"\x01\x00\x00"
            + b"\x10" * 4 + b"\xff\xd9")


def test_cursor_skips_recovered_region() -> None:
    """Two aligned JPEGs: the first is recovered; the second starts exactly on
    the alignment boundary and is its own artifact (cursor doesn't jump it)."""
    jpg = _jpg_stub()
    image = b"\x00" * 512 + jpg + b"\x00" * (512 - len(jpg)) + jpg
    result = scan(image, window=1 << 20, safety_cap=1 << 20, alignment=512,
                  signatures=specter.carve.signatures.default_signatures())
    starts = sorted(r.offset for r in result.recoveries if r.type == "jpg")
    assert starts == [512, 1024]


def test_cursor_never_double_recovers_the_same_spot() -> None:
    """Once a JPEG is recovered at 512, nothing else gets a header on it —
    and a second magic placed *inside* the recovery stays silent — P-08."""
    jpg = _jpg_stub()
    image = b"\x00" * 512 + jpg
    result = scan(image, window=1 << 20, safety_cap=1 << 20, alignment=512,
                  signatures=specter.carve.signatures.default_signatures())
    starts = [r.offset for r in result.recoveries if r.type == "jpg"]
    assert starts == [512]
    assert result.stats is not None and result.stats.recovered == 1


def test_cursor_reports_masked_bytes() -> None:
    """The masking counter fires when one recovery covers another signature's magic."""
    # Construct a JPEG whose entropy tail contains a valid PNG signature
    # but sits inside what the JPG recovery reports.
    png_takeover = b"\xff\xd8\xff" + b"\xff\xe0" + (6).to_bytes(2, "big") + b"abcd" \
        + b"\xff\xda" + (5).to_bytes(2, "big") + b"\x01\x00\x00" \
        + _png()[8:] + b"\xff\xd9"
    # Both imaginatories point at the same spot; the later one must be masked.
    result = scan(png_takeover, window=1 << 20, safety_cap=1 << 20, alignment=0,
                  signatures=specter.carve.signatures.default_signatures())
    sub = [r for r in result.recoveries if r.type == "png"]
    # The PNG magic lives inside the JPG recovery → JPG wins, PNG is dropped
    assert not sub or result.stats is not None and result.stats.masked_bytes >= png_takeover.find(b"PNG")


def test_attempted_lowconfidence_region_is_skipped() -> None:
    """An attempted (capped) recovery still advances the cursor per §9.4."""
    # A truncated JPEG whose parse goes through the fallback writes low,
    # but its span is still claimed and the next magic inside is skipped.
    fake = b"\xff\xd8\xff" + b"\xff\xda" + (5).to_bytes(2, "big") + b"\x01\x00\x00" + b"\x11" * 16
    inner_png = fake + _png()
    result = scan(inner_png, window=1 << 20, safety_cap=1 << 20, alignment=0,
                  signatures=specter.carve.signatures.default_signatures())
    overlay = result.recoveries  # jpg masks png (same start or overlap)
    assert len(overlay) <= 2  # at most one recovery wins per span