"""PNG recovery — chunk walk with CRC validation (§9.2, P-06 note).

Full 8-byte signature, then chunks of ``length | type | data | CRC32``.
Ends at ``IEND``. CRC validation is why PNG almost never false-positives —
but it also gives the O(1) rejection rule (P-07): the **first** chunk's CRC
is checked before any further walking, so a bogus candidate dies immediately.

Failure rules: a malformed chunk mid-stream (bad CRC, bogus length) ends the
recovery at the previous chunk boundary, low-confidence — never an exception.
"""

from __future__ import annotations

import zlib

from specter.carve.types import Recovery

SIGNATURE = b"\x89PNG\r\n\x1a\n"
_IEND = b"IEND"


def _chunk_crc_ok(buf: bytes, pos: int, length: int) -> bool:
    crc_against = bytes(buf[pos + 4 : pos + 8 + length])
    stored = int.from_bytes(bytes(buf[pos + 8 + length : pos + 12 + length]), "big")
    return (zlib.crc32(crc_against) & 0xFFFFFFFF) == stored


def parse(buf: bytes, offset: int, cap: int) -> Recovery | None:
    """Walk chunks for a PNG at ``offset``; reject quickly on CRC failure."""
    size = len(buf)
    limit = min(offset + cap, size)
    pos = offset + 8
    if offset + 8 > size or bytes(buf[offset : offset + 8]) != SIGNATURE:
        return None

    first = True
    try:
        while True:
            if pos + 12 > limit:
                raise ValueError  # malformed: no room for a chunk header
            length = int.from_bytes(bytes(buf[pos : pos + 4]), "big")
            ctype = bytes(buf[pos + 4 : pos + 8])
            total = 12 + length
            if pos + total > limit:
                raise ValueError  # chunk runs past the cap/image end
            if not _chunk_crc_ok(buf, pos, length):
                if first:
                    return None  # P-07: O(1) rejection on the first chunk
                raise ValueError  # later CRC failure: truncate with low confidence
            pos += total
            first = False
            if ctype == _IEND:
                return Recovery("png", offset, pos - offset, "high")
    except ValueError:
        # Malformed mid-stream: recover what walked cleanly, low confidence.
        if pos == offset + 8:
            return None  # nothing before the first chunk — not a PNG
        return Recovery("png", offset, pos - offset, "low")