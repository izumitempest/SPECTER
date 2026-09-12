"""Blob garbage collection — two-phase (E-02) and reconciliation (§4.1.5).

Blobs are never deleted inside a request or worker transaction. GC runs
periodically and on job completion:

- **Phase 1** — `BEGIN IMMEDIATE`; delete rows with ``refcount = 0``; commit.
- **Phase 2** — `BEGIN IMMEDIATE` used purely as a cross-process mutex (no
  writes); re-verify each row is still absent (a recreated row means a
  concurrent writer won — skip); unlink; commit empty. At most 256 unlinks
  per pass; the rest defer to the next pass.

Failure rules (FS-mutation totality): every unlink/replace site catches and
skips Windows ``PermissionError`` (file open elsewhere) and POSIX ``ENOENT``
(already gone); skipped paths retry next pass; no exception escapes the job.
Reconciliation runs both directions: files without rows = orphans from
crashed writers (deleted); rows without files = flagged ``lost``. Temp files
carry the owning job ID and are swept by active-set, not by age alone.

GC emits one summary audit entry — orphans removed, rows flagged lost — so
the trail stays complete without per-blob noise. The backstop is the image
itself: a lost blob costs a re-carve, never evidence.

Tasks: M2-7.
"""

from __future__ import annotations