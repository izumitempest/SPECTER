"""Known-file hash sets, disk-backed (§10.3, P-11).

NSRL-class lists are far too large for RAM on the target machine, so they are
compiled once from CSV into a sorted binary array of 32-byte hashes, looked
up by binary search with zero resident memory, plus an optional Bloom
prefilter (~180 MB at 1% false-positive for 150M entries).

A false "known" verdict hides an artifact from review — the harmful,
asymmetric error. So a Bloom hit is **always confirmed** by exact binary
search before the artifact is tagged as known.

Tasks: M3-5.
"""

from __future__ import annotations