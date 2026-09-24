"""SQLite schema v1 and connection management.

Spec: §4 (WAL mode, ``busy_timeout``, single-analyst profile), §8 (the case
database runs ``synchronous=FULL`` — that is what makes audit co-commitment
work, P-04c), §15 (data model: 11 tables). There is no ``chunks`` table —
per-chunk hashes live in the sidecar file (P-03).

Connection defaults: ``PRAGMA journal_mode=WAL``; ``busy_timeout`` (5000 ms);
``foreign_keys=ON``; and for the case database ``synchronous=FULL``
(audit co-commitment). A ``schema_version`` table tracks migrations.
"""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1

#: The 11 tables of schema v1, in §15 order.
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

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('examiner', 'reviewer', 'admin')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('open', 'closed')),
    created_by INTEGER NOT NULL REFERENCES users (id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases (id),
    path TEXT NOT NULL,
    size INTEGER NOT NULL,
    whole_image_sha256 TEXT,
    merkle_root TEXT,
    chunk_size INTEGER NOT NULL DEFAULT 4194304,  -- 4 MiB (§7.1); set at hash
    chunks_path TEXT,
    chunks_file_sha256 TEXT,
    verified_copy_path TEXT,
    stat_size INTEGER,
    stat_mtime INTEGER,
    stat_inode INTEGER,
    registered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blobs (
    sha256 TEXT PRIMARY KEY,
    storage_path TEXT NOT NULL,
    size INTEGER NOT NULL,
    refcount INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'lost'))
);

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY,
    image_id INTEGER NOT NULL REFERENCES images (id),
    type TEXT NOT NULL,
    offset INTEGER NOT NULL,
    length INTEGER NOT NULL,
    confidence TEXT NOT NULL,
    content_sha256 TEXT NOT NULL REFERENCES blobs (sha256),
    entropy_profile TEXT,
    flags TEXT,
    carved_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS loose_files (
    id INTEGER PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases (id),
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    signature TEXT,
    mismatch_flag INTEGER NOT NULL DEFAULT 0,
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases (id),
    type TEXT NOT NULL,
    params TEXT,
    status TEXT NOT NULL CHECK (status IN (
        'queued', 'running', 'done', 'failed', 'paused_disk'
    )),
    submitted_by INTEGER NOT NULL REFERENCES users (id),
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS case_members (
    user_id INTEGER NOT NULL REFERENCES users (id),
    case_id INTEGER NOT NULL REFERENCES cases (id),
    role_in_case TEXT NOT NULL CHECK (role_in_case IN ('examiner', 'reviewer')),
    PRIMARY KEY (user_id, case_id)
);

CREATE TABLE IF NOT EXISTS audit_entries (
    id INTEGER PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases (id),
    seq INTEGER NOT NULL,
    prev_hash TEXT NOT NULL,
    payload TEXT NOT NULL,
    entry_hash TEXT NOT NULL,
    actor TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    UNIQUE (case_id, seq)
);

CREATE TABLE IF NOT EXISTS manifests (
    id INTEGER PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases (id),
    exported_at TEXT NOT NULL,
    image_roots TEXT NOT NULL,
    audit_head TEXT NOT NULL,
    audit_seq INTEGER NOT NULL,
    tool_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS triage_findings (
    id INTEGER PRIMARY KEY,
    artifact_id INTEGER NOT NULL REFERENCES artifacts (id),
    kind TEXT NOT NULL,
    offset INTEGER NOT NULL,
    length INTEGER NOT NULL,
    detail TEXT
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    """Open a connection with the SPECTER pragmas, creating the schema if needed."""
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=FULL")
    conn.executescript(_SCHEMA_SQL)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
    )
    return conn