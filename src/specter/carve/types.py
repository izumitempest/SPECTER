"""Shared types for the carving engine (§9).

``Recovery`` is what a parser returns when a candidate checks out: the file
type, the byte range in the image, and how confident we are. ``confidence``
is ``"high"`` for a clean structural walk, ``"low"`` for a cap-bounded or
truncated fallback. A parser returns ``None`` for an O(1) rejection.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Recovery:
    type: str
    offset: int
    length: int
    confidence: str  # "high" | "low"

    @property
    def end(self) -> int:
        return self.offset + self.length


# A parser sees the whole read-only buffer, the candidate offset, and the
# safety cap. It returns a Recovery, or None to reject the candidate.
# It must never raise and never loop unboundedly (§9.3).
Parser = object  # typing placeholder; narrowed when parsers land