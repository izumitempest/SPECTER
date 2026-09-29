"""ZIP (and OOXML) recovery — local-header walk (§9.2).

Header ``50 4B 03 04``. Walks local file headers. When stored sizes are
zero (streaming data descriptors), falls back to a backward scan from the
end-of-central-directory record ``50 4B 05 06``.

OOXML documents (docx/xlsx/pptx) are also ZIP containers; refinement to a
specific type happens at loose-file import time via ``[Content_Types].xml``
(§10.2), not here — the carver reports them as ZIP.

Tasks: M1-1.
"""

from __future__ import annotations

from specter.carve.types import Recovery

SIGNATURE = b"PK\x03\x04"
_EOCD = b"PK\x05\x06"


def parse(buf: bytes, offset: int, cap: int) -> Recovery | None:
    """Walk ZIP local headers, falling back to EOCD scan on zero sizes."""
    size = len(buf)
    limit = min(offset + cap, size)
    if offset + 4 > limit or bytes(buf[offset : offset + 4]) != SIGNATURE:
        return None

    # Try local-header walk first.
    try:
        pos = offset
        seen_headers = 0
        while True:
            sig = bytes(buf[pos : pos + 4])
            if sig == _EOCD:
                # Proper end: validate the EOCD record is plausible.
                if pos + 22 > limit:
                    raise ValueError
                cd_count = int.from_bytes(bytes(buf[pos + 10 : pos + 12]), "little")
                if cd_count != seen_headers and seen_headers > 0:
                    raise ValueError  # mismatch: advertisement doesn't match walk
                eocd_len = 22 + int.from_bytes(bytes(buf[pos + 20 : pos + 22]), "little")
                if pos + eocd_len > limit:
                    eocd_len = limit - pos
                return Recovery("zip", offset, pos + eocd_len - offset, "high")
            # Only now do we require room for a *local file header*.
            if pos + 30 > limit:
                raise ValueError
            if sig != SIGNATURE:
                # Not another local header — end of local headers, but the
                # EOCD should follow. Look for it nearby.
                window_start = pos
                eocd_pos = buf.find(_EOCD, window_start, limit)
                if eocd_pos == -1:
                    raise ValueError
                eocd_len = 22 + int.from_bytes(bytes(buf[eocd_pos + 20 : eocd_pos + 22]), "little")
                if eocd_pos + eocd_len > limit:
                    eocd_len = limit - eocd_pos
                return Recovery("zip", offset, eocd_pos + eocd_len - offset, "high")
            # Local header layout (all LE):
            #   0  sig(4) | 4 version(2) | 6 flags(2) | 8 method(2)
            #   10 mtime(2) | 12 mdate(2) | 14 crc32(4) | 18 csize(4)
            #   22 usize(4) | 26 name_len(2) | 28 extra_len(2) | 30 name..
            flags = int.from_bytes(bytes(buf[pos + 6 : pos + 8]), "little")
            comp_size = int.from_bytes(bytes(buf[pos + 18 : pos + 22]), "little")
            uncomp_size = int.from_bytes(bytes(buf[pos + 22 : pos + 26]), "little")
            name_len = int.from_bytes(bytes(buf[pos + 26 : pos + 28]), "little")
            extra_len = int.from_bytes(bytes(buf[pos + 28 : pos + 30]), "little")
            if comp_size == 0 and uncomp_size != 0 and not (flags & 0x08):
                raise ValueError  # zero csize without streaming-descriptor flag
            body_end = pos + 30 + name_len + extra_len + comp_size
            if body_end > limit:
                raise ValueError
            pos = body_end
            seen_headers += 1
    except ValueError:
        # Fallback: backward scan for EOCD within cap.
        w = bytes(buf[offset:limit])
        rfind = w.rfind(_EOCD)
        if rfind == -1:
            return None  # no EOCD in range → not a ZIP at this offset
        eocd_len = 22 + int.from_bytes(w[rfind + 20 : rfind + 22], "little")
        end = offset + rfind + min(eocd_len, len(w) - rfind)
        return Recovery("zip", offset, end - offset, "low")