"""ProcessPoolExecutor wiring (§5, E-06).

Read-only mmap pages are shared across workers, so the pool is memory-frugal
for CPU-bound stages (chunk hashing, triage). The carve scan loop does not go
through the pool — it is inherently sequential (E-06).
"""

from __future__ import annotations