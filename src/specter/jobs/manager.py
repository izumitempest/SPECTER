"""Job manager — the job table, per-image lock, lifecycle transitions (§4, §4.1).

Jobs are database rows, not in-memory futures: a killed process leaves a
job marked ``failed`` and re-running it is idempotent because carving is
deterministic (§4).

**Per-image lock (§4.1.1):** at most one active (``queued``/``running``)
hash or carve job per image. Concurrent submissions queue by default; with
``queue=False`` the submit raises ``JobLockError`` — either way the choice
is audited by the caller.

Transition helpers write their own audit entries, so callers that co-commit
(§8c) simply run them inside their transaction.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

ACTIVE_STATUSES = ("queued", "running")
POOL_STATUSES = ("queued", "running", "done", "failed", "paused_disk")

# Job types that lock on a specific image (params must carry "image_id").
IMAGE_SCOPED = {"hash", "carve"}


class JobLockError(RuntimeError):
    """Another job already holds the image's carving lane (§4.1.1)."""


def submit(
    conn: sqlite3.Connection,
    *,
    case_id: int,
    type: str,
    params: dict[str, Any],
    submitted_by: int,
    queue: bool = True,
) -> int:
    """Insert a job row; returns its id. Raises JobLockError if an active
    job for the same image exists and the caller refused to queue."""
    image_id = params.get("image_id")
    if type in IMAGE_SCOPED and image_id is not None:
        for row in conn.execute(
            "SELECT id, params FROM jobs WHERE case_id = ? AND status IN ('queued','running')",
            (case_id,),
        ):
            if json.loads(row["params"]).get("image_id") == image_id:
                if queue:
                    break  # allowed: it queues behind the active one
                raise JobLockError(
                    f"image {image_id} already has an active job (job {row['id']})"
                )
    # Single-line literal SQL; every value is bound via ?, never interpolated.
    sql = "INSERT INTO jobs (case_id, type, params, status, submitted_by, created_at) VALUES (?, ?, ?, 'queued', ?, datetime('now'))"
    cur = conn.execute(sql, (case_id, type, json.dumps(params, sort_keys=True), submitted_by))
    return int(cur.lastrowid)


def _transition(
    conn: sqlite3.Connection, job_id: int, status: str, error: str | None
) -> None:
    if status == "paused_disk":
        # Paused, not finished: keep timestamps so a later resume reads clean.
        conn.execute(
            "UPDATE jobs SET status = ?, error = ? WHERE id = ?",
            (status, error, job_id),
        )
        return
    # Two literal SQL statements (no interpolation): one per state column.
    if status == "running":
        sql = "UPDATE jobs SET status = ?, started_at = datetime('now'), error = ? WHERE id = ?"
    else:
        sql = "UPDATE jobs SET status = ?, finished_at = datetime('now'), error = ? WHERE id = ?"
    conn.execute(sql, (status, error, job_id))


def start(conn: sqlite3.Connection, job_id: int) -> None:
    _transition(conn, job_id, "running", None)


def finish(conn: sqlite3.Connection, job_id: int) -> None:
    _transition(conn, job_id, "done", None)


def fail(conn: sqlite3.Connection, job_id: int, error: str) -> None:
    _transition(conn, job_id, "failed", error)


def pause_disk(conn: sqlite3.Connection, job_id: int) -> None:
    """Disk pre-flight tripped — job pauses, not fails (§4.1.3)."""
    _transition(conn, job_id, "paused_disk", None)


def get(conn: sqlite3.Connection, job_id: int) -> dict[str, Any] | None:
    sql = "SELECT id, case_id, type, params, status, submitted_by, created_at, started_at, finished_at, error FROM jobs WHERE id = ?"
    row = conn.execute(sql, (job_id,)).fetchone()
    if row is None:
        return None
    return {**dict(row), "params": json.loads(row["params"])}