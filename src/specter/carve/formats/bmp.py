"""BMP recovery — validate, clamp, cap-fallback (§9.2).

Header ``42 4D`` ("BM"). The 32-bit size field at offset 2 is frequently
wrong in the wild (0, absurdly large, or short). We trust it only if it's
plausible *and* fits inside the cap; otherwise we clamp + flag low confidence.

Tasks: M1-2.
"""

from __future__ import annotations

from specter.carve.types import Recovery

SIGNATURE = b"BM"


def parse(buf: bytes, offset: int, cap: int) -> Recovery | None:
    size = len(buf)
    limit = min(offset + cap, size)
    if offset + 14 > limit or bytes(buf[offset : offset + 2]) != SIGNATURE:
        return None  # minimum header won't even fit — not a BMP

    declared = int.from_bytes(bytes(buf[offset + 2 : offset + 6]), "little")
    if declared == 0:
        return Recovery("bmp", offset, limit - offset, "low")
    if declared > cap or offset + declared > limit:
        return Recovery("bmp", offset, limit - offset, "low")
    return Recovery("bmp", offset, declared, "high")