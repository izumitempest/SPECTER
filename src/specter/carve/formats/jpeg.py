"""JPEG recovery — a two-mode state machine (§9.2, P-06, E-01).

Header ``FF D8 FF``. The walk alternates between two modes:

- **Marker mode.** Markers are length-delimited. APPn/DQT/SOF/DHT segments
  are consumed opaquely by length — so an EXIF thumbnail's internal EOI never
  ends the walk by mistake. Leading ``FF`` fill bytes are skipped before each
  marker code (``FF FF FF D9`` is EOI with two fills).
- **Entropy mode** (after SOS). ``FF 00`` = stuffed literal (consume both);
  ``FF D0–D7`` = restart marker (consume both); ``FF FF`` = fill (consume one,
  re-peek); any other ``FF xx`` = a real marker, so return to marker mode.
  Progressive JPEGs re-enter entropy mode at each SOS.

A dangling ``FF`` with no byte to peek (at the cap or image end) takes the
fallback path — treated as "no EOI found", low-confidence, never a marker
parse (E-01+). With no EOI inside the cap: fall back to the last ``FF D9``
within the cap, low-confidence; otherwise cap-bounded.

Entropy-mode scanning is the JPEG parser's cost: ~4K Python iterations per
MB, ~1–2 s/GB. It is profiled in M1's clean-image throughput run, not the
P-09 density gate (E-10).

Tasks: M0-10 (baseline fixtures), M1-3 (full state machine + cjpeg recipes).
"""

from __future__ import annotations