"""Tests for the content-addressed blob store (M1-6, P-01, E-02/E-04)."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from specter.store.blob import BlobStore


def _case_db(tmp: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(tmp / "t.db"))
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS blobs (sha256 TEXT PRIMARY KEY, storage_path TEXT, size INTEGER, refcount INTEGER, status TEXT)"
    )
    return conn


def test_add_once_writes_file(tmp_path: Path) -> None:
    store = BlobStore(tmp_path)
    store.root.mkdir(parents=True, exist_ok=True)
    conn = _case_db(tmp_path)
    content = b"test-blob-bytes-for-carving"
    sha = hashlib.sha256(content).hexdigest()
    ref = store.add(conn, content)
    assert ref.sha256 == sha
    # Not yet renamed — still in temp state until commit_staged.
    assert not (store.root / sha).exists()
    conn.commit()
    pairs = store.commit_staged(conn, [ref])
    assert pairs == [(store.root / (sha + ".carving"), store.root / sha)]
    assert (store.root / sha).read_bytes() == content
    conn.close()


def test_read_round_trip(tmp_path: Path) -> None:
    store = BlobStore(tmp_path)
    store.root.mkdir(parents=True, exist_ok=True)
    conn = _case_db(tmp_path)
    content = b"blob\x00binary\x00content"
    ref = store.add(conn, content)
    conn.commit()
    store.commit_staged(conn, [ref])
    back = store.read(ref.sha256)
    assert back == content
    conn.close()


def test_idempotent_reuse_when_file_known(tmp_path: Path) -> None:
    """Second add of same content: refcount bumps, temp cleanup runs."""
    store = BlobStore(tmp_path)
    store.root.mkdir(parents=True, exist_ok=True)
    conn = _case_db(tmp_path)
    content = b"same bytes"
    ref1 = store.add(conn, content)
    conn.commit()
    # simulate rename of ref1
    tmp1 = store.root / (ref1.sha256 + ".carving")
    os_final = store.root / ref1.sha256
    tmp1.rename(os_final)
    ref2 = store.add(conn, content)   # row exists; file exists
    conn.commit()
    store.commit_staged(conn, [ref2])
    # Both reads work; refcount is 2.
    assert store.read(ref1.sha256) == content
    row = conn.execute("SELECT refcount FROM blobs WHERE sha256 = ?", (ref1.sha256,)).fetchone()
    assert row[0] == 2
    conn.close()
