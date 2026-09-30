"""SQLite recovery — page-size × page-count math (§9.2).

Signature is the 16-byte ``SQLite format 3\\0``. Page size lives at offset
16 (value ``1`` = 65536), page count at offset 28; size = pages × page_size.
Stale counts are flagged (the page count lags real growth until a checkpoint)
and we degrade to low-confidence instead of failing.

Tasks: M1-2.
"""

from __future__ import annotations

from specter.carve.types import Recovery

SIGNATURE = b"SQLite format 3\x00"


def parse(buf: bytes, offset: int, cap: int) -> Recovery | None:
    size = len(buf)
    limit = min(offset + cap, size)
    if offset + 100 > limit or bytes(buf[offset : offset + 16]) != SIGNATURE:
        return None  # header alone must fit, and must match exactly

    page_size_raw = int.from_bytes(bytes(buf[offset + 16 : offset + 18]), "big")
    page_size = 65536 if page_size_raw == 1 else page_size_raw
    if page_size < 512 or page_size > 65536 or (page_size & (page_size - 1)) != 0:
        return None  # must be a power of two in [512, 65536]

    page_count = int.from_bytes(bytes(buf[offset + 28 : offset + 32]), "big")
    if page_count == 0:
        return Recovery("sqlite", offset, limit - offset, "low")

    total = page_size * page_count
    if offset + total > limit:
        # Stale page count: report what fits and mark low (spec §9.2).
        return Recovery("sqlite", offset, limit - offset, "low")
    return Recovery("sqlite", offset, total, "high")