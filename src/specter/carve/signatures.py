"""The signature table — the registry of supported format parsers (§9.2).

Maps header magic bytes to the parser for that format. Header bytes are the
cheap trigger; the parser's own validation does the real work, and every
candidate is rejected in O(1) before any expensive scan (P-07).

Each entry is a ``Signature``:

- ``magic``:        the byte string the scanner searches for.
- ``type``:         the artifact type label written to the DB.
- ``magic_delta``:  header_start = match_offset + magic_delta. Only MP4 uses
                    a non-zero delta (its magic ``ftyp`` sits +4 into the box).

The table's version is recorded in the audit config snapshot (§8), so any
change to carving behavior is traceable to a table version.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from specter.carve.types import Recovery

#: Signature-table version, recorded in the audit config snapshot (§8).
SIGNATURE_TABLE_VERSION = 1

ParserFn = Callable[[bytes, int, int], "Recovery | None"]  # (buffer, offset, cap)


@dataclass(frozen=True)
class Signature:
    type: str
    magic: bytes
    parse: ParserFn
    magic_delta: int = 0


# M0-10 ships jpeg + png. M1-1 adds gif + zip. M1-2 registers the remaining
# five (pdf, pe, sqlite, bmp, mp4) as they land.
def default_signatures() -> list[Signature]:
    """The live registry (built per call; parser imports stay lazy)."""
    from specter.carve.formats import gif, jpeg, png, zip as zip_fmt

    return [
        Signature("jpg", b"\xff\xd8\xff", jpeg.parse),
        Signature("png", png.SIGNATURE, png.parse),
        Signature("gif", gif.SIGNATURE, gif.parse),
        Signature("zip", zip_fmt.SIGNATURE, zip_fmt.parse),
    ]
