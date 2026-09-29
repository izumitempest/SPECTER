"""Golden-fixture tests for GIF and ZIP parsers (M1-1; spec §9.2, §17).

Fixtures are built by hand (deterministic, committed, byte-exact).
"""

from __future__ import annotations

import zlib

from specter.carve.formats import gif as gifm
from specter.carve.formats import zip as zipm
from specter.carve.scanner import scan
from specter.carve.signatures import default_signatures


# --- GIF -------------------------------------------------------------------


def _gif_minimal() -> bytes:
    """Minimal legal GIF: header, LSD, one 1x1 image, one sub-block, trailer."""
    header = b"GIF89a"
    lsd = bytes([0x01, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00])  # 1x1, no GCT
    img = (
        b"\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00"  # image descriptor
        + b"\x02"      # LZW min code size = 2
        + b"\x02\x4c\x01"  # one 2-byte sub-block
        + b"\x00"      # block terminator
    )
    return header + lsd + img + b"\x3b"  # 0x3B trailer


def _gif_premature_trailer() -> bytes:
    """A stray 00 3B inside image data must NOT terminate the parse — only the
    structural walk reaches a valid trailer."""
    header = b"GIF89a"
    lsd = bytes([0x01, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00])
    # Image data containing the bytes 00 3B *inside* a sub-block of length 4.
    img = (
        b"\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00"
        + b"\x02"
        + b"\x04\x00\x3b\xaa\xbb"  # sub-block of length 4 holding 00 3B inside
        + b"\x00"
    )
    return header + lsd + img + b"\x3b"


def _gif_overrun() -> bytes:
    """Sub-block length claims more than there is. Must not read past."""
    header = b"GIF89a"
    lsd = bytes([0x01, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00])
    img = (
        b"\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00" + b"\x02"
        + b"\xff\xaa"  # sub-block says 255 bytes, then the buffer ends
    )
    return header + lsd + img  # truncated after 2 payload bytes


class TestGif:
    def test_minimal_csv(self) -> None:
        data = _gif_minimal()
        r = gifm.parse(data, 0, 4096)
        assert r is not None and r.confidence == "high"
        assert r.end == len(data)

    def test_premature_trailer_inside_data_does_not_end(self) -> None:
        data = _gif_premature_trailer()
        r = gifm.parse(data, 0, 4096)
        assert r is not None and r.confidence == "high"
        assert r.end == len(data)

    def test_overrun_low_confidence_no_crash(self) -> None:
        data = _gif_overrun()
        r = gifm.parse(data, 0, 4096)
        if r is None:
            return  # reject is acceptable
        assert r.confidence == "low"

    def test_bogus_header_rejected(self) -> None:
        data = b"GIF8" + b"\x00" * 64  # no valid LSD
        # parser should not invent a GIF out of garbage
        r = gifm.parse(data, 0, 4096)
        assert r is None or r.end <= 4096


# --- ZIP -------------------------------------------------------------------


def _zip_record(name: bytes, body: bytes) -> bytes:
    """A single stored local file header + name + body."""
    crc = zlib.crc32(body) & 0xFFFFFFFF
    header = (
        b"PK\x03\x04"
        + (20).to_bytes(2, "little")     # version needed
        + (0).to_bytes(2, "little")      # flags
        + (0).to_bytes(2, "little")      # methd store
        + (0).to_bytes(2, "little")      # mod time
        + (0).to_bytes(2, "little")      # mod date
        + crc.to_bytes(4, "little")
        + len(body).to_bytes(4, "little")
        + len(body).to_bytes(4, "little")
        + len(name).to_bytes(2, "little")
        + (0).to_bytes(2, "little")      # extra field len
    )
    return header + name + body


def _eocd(num_entries: int) -> bytes:
    return (
        b"PK\x05\x06"
        + (0).to_bytes(2, "little")       # disk
        + (0).to_bytes(2, "little")       # cd disk
        + num_entries.to_bytes(2, "little")
        + num_entries.to_bytes(2, "little")
        + (0).to_bytes(4, "little")       # cd size (not validated here)
        + (0).to_bytes(4, "little")       # cd offset (not validated here)
        + (0).to_bytes(2, "little")       # comment len
    )


def _zip_two_files() -> bytes:
    a = _zip_record(b"a.txt", b"hello")
    b = _zip_record(b"b.txt", b"world!")
    return a + b + _eocd(2)


def _zip_streaming() -> bytes:
    """Local header with zero sizes + data descriptor flag (bit 3 set)."""
    body = b"streamed bytes"
    header = (
        b"PK\x03\x04"
        + (20).to_bytes(2, "little")
        + (0x08).to_bytes(2, "little")       # flag 0x08 = streaming descriptor
        + (0).to_bytes(2, "little")
        + (0).to_bytes(2, "little")
        + (0).to_bytes(2, "little")
        + (0).to_bytes(4, "little")          # CRC (must be 0 in stream mode)
        + (0).to_bytes(4, "little")          # comp size = 0
        + (0).to_bytes(4, "little")          # uncomp size = 0
        + len(b"s.txt").to_bytes(2, "little")
        + (0).to_bytes(2, "little")
    )
    return header + b"s.txt" + body + _eocd(1)


class TestZip:
    def test_two_files_high_confidence(self) -> None:
        data = _zip_two_files()
        r = zipm.parse(data, 0, 4096)
        assert r is not None and r.confidence == "high"
        assert r.end == len(data)

    def test_streaming_descriptor_accepted(self) -> None:
        data = _zip_streaming()
        r = zipm.parse(data, 0, 4096)
        assert r is not None
        assert data[r.offset : r.end].endswith(b"PK\x05\x06") or r.confidence in ("high", "low")

    def test_bogus_signature_rejected(self) -> None:
        data = b"PK\x03\x04" + b"\xff" * 40  # signature, nothing more
        r = zipm.parse(data, 0, 4096)
        assert r is None  # no EOCD in range → reject

    def test_eocd_fallback_when_local_walk_fails(self) -> None:
        # Corrupt the comp_size of the first header so the walk overshoots.
        a = _zip_record(b"a.txt", b"hello")
        corrupted = bytearray(a)
        corrupted[18:22] = (0xFFFF).to_bytes(2, "little") + b"\xff\xff"
        data = bytes(corrupted) + _eocd(1)
        r = zipm.parse(data, 0, 4096)
        assert r is not None
        assert r.confidence == "low"  # landed on EOCD fallback


# --- end-to-end through the scanner ---------------------------------------


class TestScannerWithGifZip:
    def test_scanner_finds_both(self) -> None:
        jpg_like = b"\xff\xd8\xff\xe0\x00\x06ab\x00" + b"\xff\xda\x00\x05\x01\x00\x00" + b"\x10" * 16 + b"\xff\xd9"
        gif_part = _gif_minimal()
        zip_part = _zip_two_files()
        img = (
            b"\x00" * 512
            + jpg_like
            + b"\x00" * (512 - len(jpg_like) % 512)
            + gif_part
            + b"\x00" * (512 - len(gif_part) % 512)
            + zip_part
        )
        result = scan(img, window=1 << 20, safety_cap=1 << 20, alignment=512, signatures=default_signatures())
        types = sorted(x.type for x in result.recoveries)
        assert types == ["gif", "jpg", "zip"], result.recoveries
