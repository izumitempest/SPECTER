"""Type-aware entropy analysis (§10.1, P-10).

Shannon entropy per 4 KiB block, but the flag is **directional per type**:
compressed formats (JPEG/PNG/ZIP/MP4) flag *low* entropy as a truncated or
corrupt carve; EXE flags high entropy as packing (e.g. UPX); PDF/SQLite/BMP
flag high entropy as encryption or misidentification.

Pinned points:

- ``block_entropy`` is the exact algorithm quoted in §10.1 — do not change it.
- Checks run over **position windows**, not whole-artifact averages: the
  truncated/corrupt signal is a tail window below the type's compressed floor
  with a normal head (P-10).
- Profiles are stored **aggregated** (head/tail/majority windows + histogram),
  never the full per-block series (§4.1.4).

Tasks: M3-1 (entropy + aggregation), M3-2 (position windows).
"""

from __future__ import annotations

from collections import Counter
import math


def block_entropy(data: bytes) -> float:
    """Shannon entropy of a block, in bits per byte. Pinned from §10.1."""
    if not data:
        return 0.0
    counts = Counter(data)
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())