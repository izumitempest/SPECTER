"""GIF recovery — structural sub-block walk (§9.2, P-06).

Header ``47 49 46 38`` ("GIF8"). The walk: 6-byte header ("GIF87a"/"GIF89a"),
7-byte logical screen descriptor (LSD), optional global color table, then a
stream of blocks. Image data uses *length-prefixed sub-blocks* — a zero
sub-block (``00``) ends each image's data — so inside LZW data a stray
``00 3B`` never ends the carve.

Descriptor layout (10 bytes total for an Image Descriptor):
``2C | left(2) top(2) width(2) height(2) packed(1)``.

Defensive rules (P-06): before each advance we bounds-check the next read
against both the safety cap and the image length; an overrun terminates with
a low-confidence flag — we never read past the candidate's region.
"""

from __future__ import annotations

from specter.carve.types import Recovery

SIGNATURE = b"GIF8"

_LSD_LEN = 7  # width(2) height(2) packed(1) bgcolor(1) aspect(1)


def parse(buf: bytes, offset: int, cap: int) -> Recovery | None:
    size = len(buf)
    limit = min(offset + cap, size)
    if offset + 6 > limit or bytes(buf[offset : offset + 4]) != SIGNATURE:
        return None  # O(1) rejection: no GIF signature

    def walk_sub_blocks(p: int) -> int:
        """Advance through length-prefixed sub-blocks; return position of the
        terminator+1. Raises ValueError on any bounds overflow (§9.3)."""
        while True:
            if p >= limit:
                raise ValueError
            n = buf[p]
            if n == 0:
                return p + 1
            if p + 1 + n > limit:
                raise ValueError
            p += 1 + n

    try:
        lsd = offset + 6  # LSD follows the 6-byte header
        if lsd + _LSD_LEN > limit:
            raise ValueError
        packed = buf[lsd + 4]              # GCT flag in bit 7
        gct = 3 * (1 << ((packed & 0x07) + 1)) if (packed & 0x80) else 0

        pos = lsd + _LSD_LEN + gct
        if pos > limit:
            raise ValueError

        walked_any = False  # P-07: reject only when zero valid blocks parsed
        while True:
            if pos >= limit:
                raise ValueError
            t = buf[pos]

            if t == 0x3B:  # trailer — valid only at a block boundary
                return Recovery("gif", offset, pos + 1 - offset, "high")

            if t == 0x2C:  # Image Descriptor (1 + 9 fields)
                if pos + 10 > limit:
                    raise ValueError
                ipacked = buf[pos + 9]       # local CT flag in bit 7
                lct = 3 * (1 << ((ipacked & 0x07) + 1)) if (ipacked & 0x80) else 0
                data_p = pos + 10 + lct      # LZW minimum-code-size byte
                if data_p >= limit:
                    raise ValueError
                walked_any = True
                pos = walk_sub_blocks(data_p + 1)

            elif t == 0x21:  # Extension: label(1) then sub-blocks
                if pos + 2 > limit:
                    raise ValueError
                walked_any = True
                pos = walk_sub_blocks(pos + 2)

            elif walked_any:
                raise ValueError  # garbage after a valid block → low recovery
            else:
                return None  # bad FIRST block → O(1) reject (P-07)
    except ValueError:
        if not walked_any:
            return None
        return Recovery("gif", offset, pos - offset, "low")