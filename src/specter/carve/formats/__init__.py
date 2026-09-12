"""Format parsers — one module per supported type (§9.2).

Contract every parser must honour:

1. **Total:** return a recovery or a rejection, never raise, never hang
   (§9.3.2).
2. **O(1) rejection first:** cheap checks (alignment, secondary signature,
   first-chunk CRC, one bounds check) happen before any expensive scan
   (P-07).
3. **Confidence flag:** every result carries a confidence level, so
   low-confidence fallbacks are visible to the analyst and to triage.

A parser receives the read-only image and a candidate offset and decides
whether a valid file of its type starts there, how far it extends, and how
confident the recovery is.
"""

from __future__ import annotations