"""MP4/MOV recovery — box chain walk (§9.2).

``ftyp`` sits at offset 4 of a box; the box itself starts 4 bytes back. From
there we chain box sizes: size 0 = "extends to end of file", size 1 = a
64-bit largesize field follows, normal sizes move to the next box. Chains
stay bounds-checked; a broken chain falls back to the cap, low-confidence.

Tasks: M1-2.
"""

from __future__ import annotations

from specter.carve.types import Recovery

FTYP = b"ftyp"


def parse(buf: bytes, offset: int, cap: int) -> Recovery | None:
    size = len(buf)
    limit = min(offset + cap, size)
    # At `offset` from the scanner's magic ("ftyp" found at P), the box start
    # is P - 4. Validate from there.
    box_start = offset
    if bytes(buf[box_start + 4 : box_start + 8]) != FTYP:
        return None

    pos = box_start
    try:
        while True:
            if pos + 8 > limit:
                raise ValueError
            box_size = int.from_bytes(bytes(buf[pos : pos + 4]), "big")
            box_type = bytes(buf[pos + 4 : pos + 8])
            if box_size == 1:
                # 64-bit largesize follows the type field.
                if pos + 16 > limit:
                    raise ValueError
                box_size = int.from_bytes(bytes(buf[pos + 8 : pos + 16]), "big")
            if box_size == 0:
                return Recovery("mp4", offset, limit - offset, "high")
            end = pos + box_size
            if end > limit:
                raise ValueError
            pos = end
            if pos >= limit:
                raise ValueError
    except ValueError:
        return Recovery("mp4", offset, limit - offset, "low")