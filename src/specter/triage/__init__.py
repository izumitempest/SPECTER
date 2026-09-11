"""Triage engine (§10).

Type-aware entropy analysis, streaming keyword search, and disk-backed
known-file (hash-set) filtering. Triage runs only over recovered artifacts —
it is bounded, never over the whole image (§5).

Layout:

- ``entropy`` — per-type directional entropy over position windows
- ``search``  — streaming keyword/regex search
- ``known``   — known-file hash sets (NSRL-style)
"""

from __future__ import annotations