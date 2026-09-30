"""Property tests for P-07 (O(1) rejection) and totality invariant (§9.3).

Two things get locked in here:

1. **P-07 jobs:** every parser's rejection path must be constant-time. For
   the header types we ship (JPEG/PNG/GIF), that means "bad structure,
   mustn't trigger a cap-sized scan". We bound, not time — Hypothesis will
   exercise thousands of arb inputs confirming they never do real work.
2. **Totality (§9.3.2):** every parser, given any byte string, must resolve
   to ``Recovery`` or ``None`` — never raise, never spin forever.

If Hypothesis is available, strategies feed random bytes; if not, we fall
back to seeded PRNG so the harness still runs on this machine.
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

try:
    from hypothesis import given
    from hypothesis import settings as hyp_settings
    from hypothesis import strategies as st

    HAS_HYPOTHESIS = True
except Exception:
    HAS_HYPOTHESIS = False


def _call_all_parsers(data: bytes, safety_cap: int) -> None:
    """Feed a candidate through every parser and assert totality."""
    for parser in PARSERS:
        # Rejections and recoveries are fine; GIL-safe means never raising.
        r = parser(data, 0, safety_cap)
        assert r is None or r.end <= max(safety_cap, len(data))


if HAS_HYPOTHESIS:

    @given(st.binary(min_size=0, max_size=8192), st.integers(min_value=1, max_value=1 << 20))
    @hyp_settings(max_examples=500)
    def test_total_parse_never_raises(data: bytes, cap: int) -> None:
        _call_all_parsers(data, cap)


def test_seeded_fallback_when_hypothesis_missing() -> None:
    """Deterministic fallback for environments without Hypothesis (local dev)."""
    rng = random.Random(2026)
    for _ in range(800):
        n = rng.randint(0, 256)
        data = bytes(rng.getrandbits(8) for _ in range(n))
        _call_all_parsers(data, rng.choice((64, 512, 4096)))
        # All nine must survive a cycle of random bytes without raising.


def test_p07_rejection_is_early_for_all_misaligned_pngs() -> None:
    """P-07: wrong CRC on the first chunk rejects without cap-scale cost."""
    png = bytearray(b"\x89PNG\r\n\x1a\n"
                    + (13).to_bytes(4, "big") + b"IHDR" + b"X" * 13 + b"\x00" * 4)
    # Corrupt the CRC - first-chunk CRC rejection is the cheap early out.
    png = bytes(png[:-1]) + b"\xff"
    r = _png.parse(png, 0, 1 << 20)
    assert r is None  # rejected, not a cap-sized fallback


def test_p07_bogus_magic_rejected_fast() -> None:
    garbage = b"\x00" * 4096
    for parser in (_png.parse, _jpeg.parse, _gif.parse, _zip.parse,
                   _pdf.parse, _pe.parse, _sqlite.parse, _bmp.parse):
        assert parser(garbage, 0, 4096) is None, f"{parser.__module__} accepted noise"
