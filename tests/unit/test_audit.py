"""Tests for the audit chain + writer (M0-8; spec §8, P-04, E-09)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from specter.audit.chain import PayloadError, canonical, entry_hash, genesis
from specter.audit.writer import append, build_payload, utc_now_iso, verify
from specter.db import connect


def _case_db(tmp_path: Path):
    """Open a fresh DB with one user + case so FK references resolve."""
    conn = connect(str(tmp_path / "case.db"))
    conn.execute(
        "INSERT INTO users (username, password_hash, role, created_at)"
        " VALUES ('alice', 'x', 'examiner', '2026-09-15T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO cases (name, status, created_by, created_at, updated_at)"
        " VALUES ('Demo', 'open', 1, '2026-09-15T00:00:00Z', '2026-09-15T00:00:00Z')"
    )
    return conn


# --- canonical serialization -------------------------------------------------


def test_canonical_sorts_keys_and_inlines() -> None:
    out = canonical({"b": 1, "a": 2})
    assert out == '{"a":2,"b":1}'


def test_genesis_is_deterministic() -> None:
    assert genesis(7) == hashlib.sha256(b"specter-genesis:7").hexdigest()


def test_entry_hash_matches_pinned_formula() -> None:
    payload = {"seq": 1, "case_id": 7, "prev_hash": genesis(7), "actor": "alice"}
    expected = hashlib.sha256(
        b"specter-audit-v1:" + canonical(payload).encode("utf-8")
    ).hexdigest()
    assert entry_hash(payload) == expected


def test_float_in_payload_rejected() -> None:
    with pytest.raises(PayloadError):
        canonical({"entropy": 7.42})


def test_nested_float_rejected() -> None:
    with pytest.raises(PayloadError):
        canonical({"metrics": {"score": 0.5}})


# --- the chain itself --------------------------------------------------------


def test_append_links_entries(tmp_path: Path) -> None:
    conn = _case_db(tmp_path)
    conn.execute("BEGIN IMMEDIATE")
    h1 = append(conn, case_id=1, actor="alice", actor_role="examiner", action="case_opened")
    conn.execute("COMMIT")
    conn.execute("BEGIN IMMEDIATE")
    h2 = append(conn, case_id=1, actor="alice", actor_role="examiner", action="image_registered")
    conn.execute("COMMIT")

    rows = conn.execute(
        "SELECT seq, prev_hash, entry_hash FROM audit_entries ORDER BY seq"
    ).fetchall()
    assert [r["seq"] for r in rows] == [1, 2]
    assert rows[0]["prev_hash"] == genesis(1)
    assert rows[1]["prev_hash"] == rows[0]["entry_hash"]
    assert rows[0]["entry_hash"] == h1 != rows[1]["entry_hash"] == h2
    conn.close()


def test_verify_intact_chain(tmp_path: Path) -> None:
    conn = _case_db(tmp_path)
    for action in ("case_opened", "image_registered", "hash_computed"):
        conn.execute("BEGIN IMMEDIATE")
        append(conn, case_id=1, actor="alice", actor_role="examiner", action=action)
        conn.execute("COMMIT")
    report = verify(conn, 1)
    assert report.ok and report.entries == 3 and report.first_break_seq is None
    conn.close()


def test_interior_edit_breaks_chain(tmp_path: Path) -> None:
    """§16.3: editing any entry breaks the chain from that point on."""
    conn = _case_db(tmp_path)
    for action in ("one", "two", "three"):
        conn.execute("BEGIN IMMEDIATE")
        append(conn, case_id=1, actor="alice", actor_role="examiner", action=action)
        conn.execute("COMMIT")

    # Tamper with entry 2's payload — its stored hash no longer recomputes,
    # and entry 3's prev_hash still points at the un-tampered hash.
    row = conn.execute("SELECT payload FROM audit_entries WHERE seq = 2").fetchone()
    tampered = json.loads(row["payload"])
    tampered["action"] = "tampered"
    conn.execute(
        "UPDATE audit_entries SET payload = ? WHERE seq = 2", (json.dumps(tampered),)
    )
    report = verify(conn, 1)
    assert not report.ok and report.first_break_seq == 2
    conn.close()


def test_suffix_deletion_boundary(tmp_path: Path) -> None:
    """Removing the last entry leaves an internally-consistent shortened chain.

    Detectable only against the manifest checkpoint (§16.3) — this test
    documents that boundary honestly.
    """
    conn = _case_db(tmp_path)
    for action in ("a", "b", "c"):
        conn.execute("BEGIN IMMEDIATE")
        append(conn, case_id=1, actor="alice", actor_role="examiner", action=action)
        conn.execute("COMMIT")
    conn.execute("DELETE FROM audit_entries WHERE seq = 3")
    assert verify(conn, 1).ok  # by design; the manifest catches this
    conn.close()


def test_delete_middle_breaks_chain(tmp_path: Path) -> None:
    conn = _case_db(tmp_path)
    for action in ("a", "b", "c"):
        conn.execute("BEGIN IMMEDIATE")
        append(conn, case_id=1, actor="alice", actor_role="examiner", action=action)
        conn.execute("COMMIT")
    conn.execute("DELETE FROM audit_entries WHERE seq = 2")
    report = verify(conn, 1)
    assert not report.ok
    conn.close()


def test_build_payload_structure_and_timestamp() -> None:
    p = build_payload(
        seq=3,
        case_id=9,
        prev_hash="0" * 64,
        actor="alice",
        actor_role="examiner",
        action="hash_computed",
        target={"image": 4},
        config_snapshot={"sig_table": 1},
        timestamp="2026-09-15T10:00:00Z",
    )
    assert p["ts"] == "2026-09-15T10:00:00Z"
    assert p["target"] == {"image": 4}
    assert p["config"]["sig_table"] == 1
    entry_hash(p)  # must be hashable (no floats)


def test_utc_now_iso_is_z_utc() -> None:
    assert utc_now_iso().endswith("Z")