"""Job orchestration — job table and worker pool (§4, §4.1, E-06).

- ``manager`` — persists jobs in the database (not in-memory futures), so a
  killed process leaves the job marked failed and re-running is idempotent.
- ``pool``   — the ProcessPoolExecutor wrapper.

Parallelism split, pinned by E-06: the carve **scan loop is sequential in one
worker** (its cursor is per-job state); the pool parallelises across jobs
(different images, under the per-image lock) and, within a job, chunk hashing
and artifact triage.
"""

from __future__ import annotations