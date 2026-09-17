"""Worker pool wrapper (§5, E-06).

A thin veneer over ``concurrent.futures.ProcessPoolExecutor``. Always used
for read-only, CPU-bound stages (chunk hashing, artifact triage) where mmap
pages are shared across the fork.

**The carve scan loop never goes through the pool:** its cursor state is
sequential per job (E-06); fetching parallelism is a design fork gated on
the P-09 density benchmark, not a v1 feature.

The slice of the surface here is ``carve_sync`` (the one-process path used
by the CLI and by tests) — the pool itself is created lazily by users that
need background parallelism.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from typing import Iterable


def make_pool(max_workers: int | None = None) -> ProcessPoolExecutor:
    """A fresh pool; caller owns lifecycle."""
    return ProcessPoolExecutor(max_workers=max_workers)


def map_parallel(fn, items: Iterable, max_workers: int | None = None) -> list:
    """Apply ``fn`` to every item across the pool; results in input order.

    Synchronous sugar for callers that don't yet code against futures.
    """
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(fn, items))