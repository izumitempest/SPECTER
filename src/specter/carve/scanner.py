"""The windowed single-pass scan loop, cursor, and candidate policy.

Spec: §9.1 (scan structure), §9.3 (defensive rules), §9.4 (cursor/dedupe),
E-06 (sequential scan; the pool parallelises *around* it, never inside it).

Design rules pinned in the spec:

- **Windows bound the scan pass, never the parsers.** The scan reads
  sequential windows (default 128 MiB) with a fixed 64-byte overlap; parsers
  read the full read-only buffer, bounded only by the safety cap.
- **Alignment filter** (default 512): candidates not at an aligned offset are
  rejected in O(1). ``alignment=0`` disables it.
- **One cursor per job.** Recovered *and* attempted (cap-bounded fallback)
  regions are skipped — a candidate below the cursor is not re-processed.
- **Masking is measured:** we track how many bytes the cursor skipped over
  (``masked_bytes``) so §16.1 can report the masking rate alongside recall.

The kernel is intentionally small and boring: per window, find all magic
offsets for all signatures, sort them, and let each parser decide. Anything
below the cursor is skipped. Total per-byte work stays in C: ``find`` on the
buffer, and each parser does its own structure-checked validation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from specter.carve.signatures import Signature, default_signatures
from specter.carve.types import Recovery

OVERLAP = 64  # ≥ longest signature; never the safety cap (P-05)


@dataclass(frozen=True)
class ScanStats:
    """Numbers the evaluator needs (§9.5, §16.1)."""

    elapsed_s: float
    bytes_scanned: int
    window_count: int
    candidates_seen: int
    candidates_rejected_o1: int  # alignment-filtered or O(1)-rejected
    candidates_parsed: int
    recovered: int
    masked_bytes: int  # bytes skipped by cursor advance (§9.4 masking)

    def mb_per_s(self) -> float:
        return self.bytes_scanned / self.elapsed_s / (1024 * 1024) if self.elapsed_s else 0.0


@dataclass
class ScanResult:
    recoveries: list[Recovery] = field(default_factory=list)
    stats: ScanStats | None = None


def scan(
    data: bytes,
    *,
    window: int = 128 * 1024 * 1024,
    safety_cap: int = 50 * 1024 * 1024,
    alignment: int = 512,
    signatures: list[Signature] | None = None,
) -> ScanResult:
    """Run the carving pass over ``data``.

    Deterministic: same bytes + same parameters → identical output list.
    """
    sigs = default_signatures() if signatures is None else signatures
    size = len(data)
    if size == 0:
        return ScanResult([], _stats(0, 0, 0, 0, 0, 0, 0, 0))

    cursor = 0
    recoveries: list[Recovery] = []
    seen = parsed = rejected_o1 = 0
    masked = 0
    windows = 0

    t0 = time.perf_counter()
    wstart = 0
    while wstart < size:
        windows += 1
        wend = min(wstart + window, size)
        # Search window extended by the overlap; parser never sees it (P-05).
        search_end = min(wend + OVERLAP, size)

        # All hits in this window, for all signatures, in offset order.
        hits: list[tuple[int, Signature]] = []
        for sig in sigs:
            pos = data.find(sig.magic, max(cursor, wstart) + sig.magic_delta, search_end + sig.magic_delta)
            while pos != -1 and pos < search_end + sig.magic_delta:
                header = pos - sig.magic_delta
                if header >= wstart and header < wend:  # claim this window only
                    hits.append((header, sig))
                pos = data.find(sig.magic, pos + 1, search_end + sig.magic_delta)
        hits.sort(key=lambda h: h[0])

        for offset, sig in hits:
            if offset < cursor:
                continue  # cursor skipped this region already (recovered/attempted)
            seen += 1
            if alignment and offset % alignment:
                rejected_o1 += 1
                continue  # P-07: O(1) rejection before any parse
            parsed += 1
            recovery = sig.parse(data, offset, safety_cap)
            if recovery is None:
                rejected_o1 += 1  # parser's own O(1) rejection
                continue
            recoveries.append(recovery)
            # Cursor advances past the recovered (or attempted) span (§9.4).
            new_cursor = recovery.end
            if new_cursor > cursor:
                masked += new_cursor - cursor
                cursor = new_cursor

        wstart = wend

    elapsed = time.perf_counter() - t0
    return ScanResult(
        recoveries,
        _stats(elapsed, size, windows, seen, rejected_o1, parsed, len(recoveries), masked),
    )


def _stats(
    elapsed: float,
    byte_count: int,
    windows: int,
    seen: int,
    o1: int,
    parsed: int,
    recovered: int,
    masked: int,
) -> ScanStats:
    return ScanStats(elapsed, byte_count, windows, seen, o1, parsed, recovered, masked)