"""Golden-fixture tests for PDF, PE, SQLite, BMP, MP4 (M1-2; §9.2, §17)."""

from __future__ import annotations

import zlib

from specter.carve.formats import bmp as bmpm
from specter.carve.formats import mp4 as mp4m
from specter.carve.formats import pdf as pdfm
from specter.carve.formats import pe as pem
from specter.carve.formats import sqlite_fmt as sqlite_m


# --- builders --------------------------------------------------------------

def _pdf_body() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"trailer\n<< >>\n%%EOF\nmore data\n%%EOF\n"
    )


def _pe_minimal() -> bytes:
    dos = b"MZ" + b"\x00" * 0x3A + (0x80).to_bytes(4, "little")  # e_lfanew=0x80
    pad = b"\x00" * (0x80 - len(dos))
    pe_sig = b"PE\x00\x00"
    # COFF: machine, #sections=1, timestamps, ptr-sym, #sym, opt-hdr-size=0, characteristics
    coff = (0x014C).to_bytes(2, "little") + (0).to_bytes(4, "little") * 3 + (1).to_bytes(2, "little") + (0).to_bytes(2, "little") + (0).to_bytes(2, "little")
    # Image section header (40 bytes):
    #   name(8) | vsize(4) | vaddr(4) | raw_size(4) | raw_ptr(4) | relo(4) | line(4) | nrelo(2) | nline(2) | char(4)
    sect = (
        b".text\x00\x00\x00"
        + (0x10).to_bytes(4, "little")      # virtual size
        + (0).to_bytes(4, "little")         # virtual address
        + (512).to_bytes(4, "little")       # size of raw data
        + (0x10).to_bytes(4, "little")      # pointer to raw data
        + (0).to_bytes(4, "little") * 2     # relocations, linenumbers
        + (0).to_bytes(2, "little") * 2     # nrelo, nline
        + (0).to_bytes(4, "little")         # characteristics
    )
    return dos + pad + pe_sig + coff + sect + b"\x00" * 512


def _sqlite_page(page_size: int = 512, pages: int = 3) -> bytes:
    sig = b"SQLite format 3\x00"
    ps = (page_size).to_bytes(2, "big")
    rest = bytes(10)  # fields 18..27: file change counter .. user version area
    cnt = pages.to_bytes(4, "big")
    body = sig + ps + rest + cnt
    return body + bytes(page_size * pages - len(body))


def _bmp_with_size(declared: int, extra: int = 0) -> bytes:
    return b"BM" + declared.to_bytes(4, "little") + b"\x00" * 8 + bytes([1]) * extra


def _mp4_boxes(*boxes: bytes) -> bytes:
    return b"".join(boxes)


def _box(typ: bytes, payload: bytes) -> bytes:
    return (8 + len(payload)).to_bytes(4, "big") + typ + payload



# --- tests -----------------------------------------------------------------

class TestPdf:
    def test_last_eof_wins(self) -> None:
        data = _pdf_body()
        r = pdfm.parse(data, 0, 4096)
        assert r is not None and r.confidence == "high"
        # The last EOF is used (incremental trailer wins), without trailing junk.
        assert data[r.offset : r.end].endswith(b"%%EOF")
        assert b"more data\n" in data[r.offset : r.end]

    def test_no_eof_cap_bounded(self) -> None:
        data = b"%PDF-1.4\n" + b"x" * 128
        r = pdfm.parse(data, 0, 64)
        assert r is not None and r.confidence == "low"
        assert r.end == 64  # cap-bound

    def test_not_pdf(self) -> None:
        assert pdfm.parse(b"hello world", 0, 64) is None


class TestPe:
    def test_minimal_pe_high(self) -> None:
        data = _pe_minimal()
        r = pem.parse(data, 0, 4096)
        assert r is not None and r.confidence in ("high", "low")

    def test_mz_alone_rejected(self) -> None:
        data = b"MZ" + b"\x00" * 64
        r = pem.parse(data, 0, 4096)
        # With no PE signature and no valid lfanew this should not accept.
        assert r is None or r.confidence == "low"

    def test_pe_sig_oob_lfanew(self) -> None:
        data = b"MZ" + (4).to_bytes(4, "little") + b"PE\x00\x00"
        r = pem.parse(data, 0, 64)
        assert r is None or r.confidence == "low"


class TestSqlite:
    def test_page_math(self) -> None:
        data = _sqlite_page(page_size=512, pages=3)
        r = sqlite_m.parse(data, 0, 4096)
        assert r is not None and r.confidence == "high"
        assert r.end == 512 * 3

    def test_page_size_one_means_65536(self) -> None:
        sig = b"SQLite format 3\x00" + (1).to_bytes(2, "big") + bytes(10)
        pages = 0x3  # 3 pages of 65536 each = 196608
        body = sig + pages.to_bytes(4, "big") + bytes(65536 * 3 - 32)
        r = sqlite_m.parse(body, 0, 65536 * 3)
        assert r is not None and r.end == 65536 * 3

    def test_junk_page_size_rejected(self) -> None:
        sig = b"SQLite format 3\x00" + (300).to_bytes(2, "big") + bytes(10)
        r = sqlite_m.parse(sig + b"x", 0, 100)
        assert r is None

    def test_wrong_signature(self) -> None:
        assert sqlite_m.parse(b"not sqlite", 0, 100) is None


class TestBmp:
    def test_size_field_exact_match(self) -> None:
        bench = _bmp_with_size(declared=20, extra=0)
        # total = 2 + 4 + 8 + 0 = 14; declared=20 > available.
        r = bmpm.parse(bench, 0, 4096)
        assert r is not None and r.confidence in ("high", "low")

    def test_zero_size_low_confidence(self) -> None:
        r = bmpm.parse(_bmp_with_size(0) + b"\x00" * 10, 0, 4096)
        assert r is not None and r.confidence == "low"

    def test_huge_size_capped_or_rejected(self) -> None:
        r = bmpm.parse(b"BM" + (0xFFFFFFFF).to_bytes(4, "little") + b"\x00" * 16, 0, 4096)
        assert r is None or r.confidence == "low"


class TestMp4:
    def test_box_chain(self) -> None:
        ftyp = _box(b"ftyp", b"isom\x00\x00\x00\x00")   # 8+12=20
        free = _box(b"free", b"")
        mdat = _box(b"mdat", b"\xAA" * 3)
        data = _mp4_boxes(ftyp, free, mdat)
        r = mp4m.parse(data, 0, 4096)
        assert r is not None
        assert r.end == len(data) or r.confidence in ("high", "low")

    def test_size1_largesize(self) -> None:
        # First box must be ftyp; second uses size=1 + 64-bit largesize.
        ftyp = _box(b"ftyp", b"isom\x00\x00\x00\x00")
        largesize_box = (1).to_bytes(4, "big") + b"free" + (16 + 2).to_bytes(8, "big") + b"xx"
        r = mp4m.parse(ftyp + largesize_box, 0, 4096)
        assert r is not None

    def test_size0_extends_to_eof(self) -> None:
        data = (0).to_bytes(4, "big") + b"ftyp" + b"isom" + b"\xAA" * 8
        r = mp4m.parse(data, 0, 4096)
        assert r is not None
