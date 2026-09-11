"""SQLite schema v1 and connection management.

Spec: §4 (WAL mode, busy_timeout, single-analyst profile), §8 (case DB runs
synchronous=FULL for audit co-commitment), §15 (data model).

Tables (schema v1, per §15): users, cases, images, blobs, artifacts,
loose_files, jobs, case_members, audit_entries, manifests, triage_findings.
There is no ``chunks`` table — per-chunk hashes live in the sidecar file
(P-03).

Conventions: integer primary keys, UTC ISO-8601 timestamps, a
``schema_version`` table for migrations.

Tasks: M0-5.
"""

from __future__ import annotations

SCHEMA_TABLES: tuple[str, ...] = (
    "users",
    "cases",
    "images",
    "blobs",
    "artifacts",
    "loose_files",
    "jobs",
    "case_members",
    "audit_entries",
    "manifests",
    "triage_findings",
)


def connect(db_path: str) -> object:
    """Open a configured connection (M0-5). Not yet implemented."""
    raise NotImplementedError("M0-5: connect")