"""PE/EXE recovery — MZ + PE validation plus section-table walk (§9.2).

Header ``4D 5A`` ("MZ"). **MZ alone** is a 2-byte signature with mass false-
positive rate; accept only if ``e_lfanew`` (offset 0x3C) points into the
image at a ``PE\\0\\0`` signature and the section table parses. Size =
max(section ``PointerToRawData + SizeOfRawData``) — explicitly computed as
exe-relative offsets, never confused with image-absolute coordinates
(those two are the masking hazard called out in §9.4).

The O(1) rejection rule (P-07): the header walk bails the moment lfanew is
out of range or the PE signature doesn't validate — never loops unboundedly.

Tasks: M1-2, M1-4.
"""

from __future__ import annotations

from specter.carve.types import Recovery

SIGNATURE = b"MZ"
_PE = b"PE\x00\x00"

_COFF_LEN = 20
_SECT_LEN = 40


def parse(buf: bytes, offset: int, cap: int) -> Recovery | None:
    """Attempt PE recovery from a candidate MZ at ``offset``.

    Returns None on hard non-match; a low-confidence capped recovery when
    structural walkability breaks down mid-way.
    """
    size = len(buf)
    limit = min(offset + cap, size)
    if offset + 64 > limit or bytes(buf[offset : offset + 2]) != SIGNATURE:
        return None

    try:
        # e_lfanew: 32-bit LE at offset+0x3C — file-offset of the PE header.
        e_lfanew = int.from_bytes(bytes(buf[offset + 0x3C : offset + 0x40]), "little")
        if e_lfanew == 0 or e_lfanew > cap:
            raise ValueError
        pe_abs = offset + e_lfanew
        if pe_abs + _COFF_LEN + 4 > limit:
            raise ValueError
        if bytes(buf[pe_abs : pe_abs + 4]) != _PE:
            raise ValueError

        n_sections = int.from_bytes(bytes(buf[pe_abs + 6 : pe_abs + 8]), "little")
        opt_hdr = int.from_bytes(bytes(buf[pe_abs + 20 : pe_abs + 22]), "little")
        sec_start = pe_abs + 4 + _COFF_LEN + opt_hdr
        if sec_start + n_sections * _SECT_LEN > limit:
            raise ValueError

        max_end = pe_abs + 4 + _COFF_LEN + opt_hdr + n_sections * _SECT_LEN
        for i in range(n_sections):
            sh = sec_start + i * _SECT_LEN
            # Section layout: raw-size at +16, raw-pointer at +20, LE.
            raw_size = int.from_bytes(bytes(buf[sh + 16 : sh + 20]), "little")
            raw_ptr = int.from_bytes(bytes(buf[sh + 20 : sh + 24]), "little")
            cand_end = raw_ptr + raw_size
            if cand_end > max_end and raw_ptr > 0:
                if offset + cand_end > limit:
                    raise ValueError
                max_end = cand_end
        if not (pe_abs - offset + 4 + _COFF_LEN <= max_end - offset <= limit - offset):
            raise ValueError
        return Recovery("exe", offset, max_end - offset, "high")
    except ValueError:
        return Recovery("exe", offset, limit - offset, "low")
    except Exception:
        # Anything else (struct.error, IndexError) is equally a low-confidence
        # outcome — the parser stays total (§9.3).
        return Recovery("exe", offset, limit - offset, "low")