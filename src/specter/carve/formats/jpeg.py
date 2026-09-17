"""JPEG recovery — a two-mode state machine (§9.2, P-06, E-01, E-01+).

Header ``FF D8 FF``. The walk has two modes:

- **Marker mode.** Markers are length-delimited; APPn/DQT/SOF/DHT are
  consumed opaquely by length, so an EXIF thumbnail's internal EOI cannot end
  the walk. Leading ``FF`` fill bytes are skipped before every marker code
  (``FF FF FF D9`` is EOI with two fills).
- **Entropy mode** (after SOS). ``FF 00`` is a stuffed literal (consume both);
  ``FF D0``–``FF D7`` are restart markers (consume both); ``FF FF`` is fill
  (consume one and re-peek); anything else is a real marker — return to
  marker mode. ``FF D9`` in marker mode is EOI. Progressive JPEGs re-enter
  entropy mode at each later SOS.

Failure rules (pinned): a dangling ``FF`` with no byte to peek (at the cap or
image end) takes the fallback, never a marker parse. No EOI within the cap →
fallback to the last ``FF D9`` within the cap, low-confidence; if none, the
cap itself is the boundary, low-confidence. Malformed structure (bad length,
unexpected marker) degrades the same way — total parsers (§9.3).
"""

from __future__ import annotations

from specter.carve.types import Recovery

_SOI = b"\xff\xd8"
_ENTROPY_SKIP = {0x00}  # stuffed literal
_STANDALONE = {0x01} | set(range(0xD0, 0xD8))  # TEM, RST0–RST7
_EOI = 0xD9
_SOS = 0xDA


class _Malformed(Exception):
    """Structure broke; degrade to the fallback path (§9.3)."""


def _skip_fills(buf: bytes, pos: int, limit: int) -> int:
    """Return the position of the marker byte after leading FF fills."""
    p = pos
    while p + 1 < limit and buf[p + 1] == 0xFF:
        p += 1
    return p


def _fallback(buf: bytes, offset: int, limit: int) -> Recovery:
    """Cap-bounded recovery: last EOI in range, else the cap itself."""
    window = bytes(buf[offset:limit])
    last = window.rfind(b"\xff\xd9")
    end = offset + last + 2 if last != -1 else limit
    return Recovery("jpg", offset, end - offset, "low")


def parse(buf: bytes, offset: int, cap: int) -> Recovery | None:
    """Attempt to recover a JPEG starting at ``offset``.

    Rejects in O(1) when there's no SOI marker at the offset. Never raises.
    """
    size = len(buf)
    limit = min(offset + cap, size)
    if offset + 2 > limit or bytes(buf[offset : offset + 2]) != _SOI:
        return None

    pos = offset + 2
    entropy = False  # marker mode at start
    try:
        while True:
            if entropy:
                f = buf.find(b"\xff", pos, limit)
                if f == -1 or f + 1 >= limit:
                    raise _Malformed  # no EOI within cap / dangling FF (E-01+)
                code = buf[f + 1]
                if code in _ENTROPY_SKIP or code in _STANDALONE or code == 0xFF:
                    pos = f + (1 if code == 0xFF else 2)
                    continue
                if code == _EOI:
                    return Recovery("jpg", offset, f + 2 - offset, "high")
                pos = f  # a real marker: back to marker mode
                entropy = False
            else:
                if pos + 1 >= limit:
                    raise _Malformed
                if buf[pos] != 0xFF:
                    raise _Malformed
                p = _skip_fills(buf, pos, limit)
                if p + 1 >= limit:
                    raise _Malformed  # fills then nothing
                code = buf[p + 1]
                if code == 0x00:
                    raise _Malformed
                if code == _EOI:
                    return Recovery("jpg", offset, p + 2 - offset, "high")
                if code == 0xD8 or code in _STANDALONE:
                    pos = p + 2
                    continue
                if p + 4 > limit:
                    raise _Malformed
                seglen = int.from_bytes(bytes(buf[p + 2 : p + 4]), "big")
                if seglen < 2 or p + 2 + seglen > limit:
                    raise _Malformed
                pos = p + 2 + seglen
                if code == _SOS:
                    entropy = True
    except _Malformed:
        return _fallback(buf, offset, limit)