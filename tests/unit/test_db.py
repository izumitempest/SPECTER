"""Unit tests for ``specter.db`` (M0-5; spec §4, §8, §15)."""

from __future__ import annotations

from pathlib import Path

from specter.db import SCHEMA_TABLES, connect


def test_connect_creates_all_eleven_tables(tmp_path: Path) -> None:
    conn = connect(str(tmp_path / "specter.db"))
    names = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    for table in SCHEMA_TABLES:
        assert table in names, f"missing table: {table}"
    conn.close()


def test_pragmas_applied(tmp_path: Path) -> None:
    conn = connect(str(tmp_path / "specter.db"))
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2  # FULL
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.close()


def test_schema_version_recorded(tmp_path: Path) -> None:
    conn = connect(str(tmp_path / "specter.db"))
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    assert row[0] == 1
    conn.close()


def test_idempotent_reconnect(tmp_path: Path) -> None:
    db = str(tmp_path / "specter.db")
    conn = connect(db)
    conn.execute(
        "INSERT INTO users (username, password_hash, role, created_at) "
        "VALUES ('a', 'hash', 'examiner', '2026-09-15T00:00:00Z')"
    )
    conn.close()
    conn2 = connect(db)
    count = conn2.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert count == 1
    conn2.close()