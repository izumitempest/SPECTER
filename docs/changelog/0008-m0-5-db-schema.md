# 0008 — M0-5 done: SQLite schema v1 and connection layer (db.py)

- **Date:** 2026-09-15
- **Type:** change
- **Spec refs:** §4 (WAL, busy_timeout, single-analyst), §8c (synchronous=FULL
  for co-commitment), §15 (data model)
- **Tag:** —

## Summary

Implemented `specter/db.py`. `connect()` opens a SQLite database in WAL mode
with a 5-second `busy_timeout`, foreign keys on, `synchronous=FULL` (the
pragma that makes audit co-commitment work, §8c), and applies schema v1 —
all eleven tables from §15: users, cases, images, blobs, artifacts,
loose_files, jobs, case_members, audit_entries, manifests, triage_findings,
plus a `schema_version` row for future migrations. Per the spec, there is no
`chunks` table — chunk hashes live in the sidecar file (P-03).

## What changed

- `src/specter/db.py` — full DDL + `connect()`. The `images` table carries
  the registration stat-metadata columns (size, mtime, inode) from §6/P-02;
  `audit_entries` enforces `UNIQUE(case_id, seq)` so the chain can't fork.
- `tests/unit/test_db.py` — 4 tests: all 11 tables created; WAL/FULL/FK
  pragmas set; schema version recorded; connect is idempotent (data survives
  reconnect).
- `docs/TASKS.md` — M0-5 marked done; changelog entry + index row.

## Verification

- DDL attributes charted to §15's table (11 entities + schema_version);
  pragma values asserted in tests (`synchronous=2` ↔ FULL in WAL mode).
  Tests run in CI (local venv is unavailable this session, see 0004).

## Next steps

- M0-6: `mmap_accessor` — read-only image mapping, POSIX/Windows, 64-bit guard.