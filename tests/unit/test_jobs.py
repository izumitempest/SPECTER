"""Tests for the job manager (M0-11; spec §4, §4.1.1, §4.1.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specter.db import connect
from specter.jobs.manager import (
    JobLockError,
    fail,
    finish,
    get,
    pause_disk,
    start,
    submit,
)


def _db(tmp_path: Path):
    conn = connect(str(tmp_path / "jobs.db"))
    conn.execute(
        "INSERT INTO users (username, password_hash, role, created_at)"
        " VALUES ('alice', 'x', 'examiner', '2026-09-15T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO cases (name, status, created_by, created_at, updated_at)"
        " VALUES ('Demo', 'open', 1, '2026-09-15T00:00:00Z', '2026-09-15T00:00:00Z')"
    )
    return conn


def test_submit_and_status_round_trip(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    jid = submit(
        conn, case_id=1, type="carve", params={"image_id": 7}, submitted_by=1
    )
    job = get(conn, jid)
    assert job is not None and job["status"] == "queued" and job["params"]["image_id"] == 7
    conn.close()


def test_per_image_lock_blocks_strict_resubmit(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    submit(conn, case_id=1, type="carve", params={"image_id": 7}, submitted_by=1)
    with pytest.raises(JobLockError):
        submit(
            conn, case_id=1, type="carve",
            params={"image_id": 7}, submitted_by=1, queue=False,
        )
    conn.close()


def test_other_image_is_not_locked(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    submit(conn, case_id=1, type="carve", params={"image_id": 7}, submitted_by=1)
    jid2 = submit(
        conn, case_id=1, type="carve", params={"image_id": 8}, submitted_by=1,
        queue=False,
    )
    assert jid2 > 0
    conn.close()


def test_finished_job_releases_the_lock(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    jid = submit(conn, case_id=1, type="carve", params={"image_id": 7}, submitted_by=1)
    start(conn, jid)
    finish(conn, jid)
    # Now it's not active, so a new job on the same image is fine.
    submit(conn, case_id=1, type="carve", params={"image_id": 7}, submitted_by=1, queue=False)
    conn.close()


def test_fail_records_error_and_timestamp(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    jid = submit(conn, case_id=1, type="hash", params={"image_id": 7}, submitted_by=1)
    start(conn, jid)
    fail(conn, jid, "boom")
    job = get(conn, jid)
    assert job["status"] == "failed" and job["error"] == "boom"
    assert job["finished_at"] is not None
    conn.close()


def test_pause_disk_keeps_started_at(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    jid = submit(conn, case_id=1, type="carve", params={"image_id": 7}, submitted_by=1)
    start(conn, jid)
    pause_disk(conn, jid)
    job = get(conn, jid)
    assert job["status"] == "paused_disk"
    assert job["started_at"] is not None and job["finished_at"] is None
    conn.close()