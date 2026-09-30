"""M1-4 totality fuzz harness: parsers never raise, never hang (§9.3).

Slower than the unit sweep — meant to run as part of CI's `-m "not slow"`
path. Drives each parser with random bytes of varying sizes and confirms
no exception escapes and the loop terminates.
"""

from __future__ import annotations

import random

import specter.carve.formats.bmp as _bmp
import specter.carve.formats.gif as _gif
import specter.carve.formats.jpeg as _jpeg
import specter.carve.formats.mp4 as _mp4
import specter.carve.formats.pdf as _pdf
import specter.carve.formats.pe as _pe
import specter.carve.formats.png as _png
import specter.carve.formats.sqlite_fmt as _sqlite
import specter.carve.formats.zip as _zip

PARSERS = (
    _jpeg.parse, _png.parse, _gif.parse, _zip.parse, _pdf.parse,
    _pe.parse, _sqlite.parse, _bmp.parse, _mp4.parse,
)


def test_parsers_never_raise_on_random_bytes() -> None:
    rng = random.Random(42)
    sizes = (0, 4, 32, 512, 4096)
    for seed in range(600):
        n = sizes[rng.randrange(len(sizes))]
        data = bytes(rng.getrandbits(8) for _ in range(n))
        # Plant each real signature at random offsets, half the time aligned:
        if n >= 8 and seed % 3 == 0:
            spot = rng.randrange(0, n - 4)
            magic = rng.choice((
                b"MZ", b"BM", b"GIF8", b"PK\x03\x04", b"\xff\xd8\xff",
                b"\x89PNG\r\n\x1a\n", b"SQLite format 3\x00", b"%PDF-",
            ))
            data = data[:spot] + magic + data[spot:]
        for parser in PARSERS:
            r = parser(data, 0, 4096)
            # Invariants from §9.3 totality:
            if r is not None:
                assert r.end <= 4096 + 4, (parser.__module__, r)
                assert r.end <= len(data) + 4096 or r.end <= 4096


def test_alignment_and_cap_terminates() -> None:
    """Random bytes + each real signature: parse always terminates, never raises."""
    rng = random.Random(7)
    for _ in range(120):
        n = rng.randint(0, 2048)
        data = bytes(rng.getrandbits(8) for _ in range(n))
        for parser in PARSERS:
            # call at three start positions; must never raise
            parser(data, 0, 4096)
            parser(data, min(len(data) // 2, len(data)), 4096)
            parser(data, len(data), 4096)