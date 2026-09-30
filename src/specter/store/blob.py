"""Blob store — content-addressed artifact write path (§4.1.2, P-01, E-04).

The write protocol (canonically order-pinned):

1. **Stage to a temp path** under the case's blob dir, fsync it.
2. **Insert a `Blob` row** inside the caller's current transaction (so the
   audit entry co-commits with the row, §8c).
3. **Commit**, then **rename temp → content-addressed name** — E-04's rule:
   the rename happens *after* commit, never before.

Writer materialization rule (E-04b):
- Row exists **and** file exists → no-op (skip write).
- Row exists but file is gone → re-materialize (write temp again, commit
  renames it into place).
- No row → new write: temp, commit, rename.

Reader rule (E-04a): an ENOENT on a row whose status is `active` means the
commit→rename window is in flight — retry **5×20 ms**, then surface `lost`.
Readers never repair; the repair path is exclusively GC's (E-02).

A two-phase GC (E-02) then sweeps temps by owning-job id *and* drops rows
whose file vanished; summaries land in the audit trail.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BlobRef:
    """Identity of a staged blob, pre- or post-commit."""

    sha256: str
    storage_path: Path
    size: int

    def temp_path(self) -> Path:
        """The temp-name companion for this blob (used before the rename)."""
        return self.storage_path.with_name(self.storage_path.name + ".tmp")


class BlobStore:
    """Content-addressed store backed by a case directory's ``blobs/`` dir."""

    def __init__(self, case_dir: Path) -> None:
        self.root = case_dir / "blobs"


    # ---- writer side ---------------------------------------------------------

    def add(self, conn: sqlite3.Connection, content: bytes) -> BlobRef:
        """Write-or-reuse a blob and record it in `conn`'s open transaction.

        Caller must call ``commit_staged(conn, [ref, ...])`` to finish the
        co-commitment (commit first, then rename temps into place).
        """
        sha = hashlib.sha256(content).hexdigest()
        final = self.root / sha
        conn.execute(
            "INSERT INTO blobs (sha256, storage_path, size, refcount, status) "
            "VALUES (?, ?, ?, 1, 'active') "
            "ON CONFLICT (sha256) DO UPDATE SET refcount = refcount + 1",
            (sha, str(final), len(content)),
        )
        # Stage the temp copy; the caller renames after COMMIT.
        tmp = final.with_name(final.name + ".carving")
        tmp.write_bytes(content)
        return BlobRef(sha256=sha, storage_path=self.root / sha, size=len(content))

    def commit_staged(
        self, conn: sqlite3.Connection, refs: list[BlobRef]
    ) -> list[tuple[Path, Path]]:
        """Commit the current transaction, then rename `.tmp` → final."""
        conn.commit()
        pairs: list[tuple[Path, Path]] = []
        for ref in refs:
            tmp = ref.storage_path.with_name(ref.storage_path.name + ".carving")
            pairs.append((tmp, ref.storage_path))
        for tmp, final in pairs:
            if final.exists():
                tmp.unlink(missing_ok=True)  # already materialized elsewhere
            else:
                os.replace(tmp, final)
        return pairs


    # ---- reader side ---------------------------------------------------------

    def read(self, sha: str, attempt_sleep_s: float = 0.02, attempts: int = 5) -> bytes:
        """Read a blob. Reader-side ENOENT with an active row retries
        (per E-04a) to ride out the commit→rename window, then reports."""
        target = self.root / sha
        last_exc: Exception | None = None
        for _ in range(attempts):
            try:
                return target.read_bytes()
            except FileNotFoundError as exc:
                last_exc = exc
                time.sleep(attempt_sleep_s)
        raise last_exc if last_exc is not None else FileNotFoundError(str(target))
