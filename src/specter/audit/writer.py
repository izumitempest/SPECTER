"""Audit writer and verifier — the co-commitment append path (§8b-c, P-04c).

The one write path (single-writer discipline): an entry is appended **inside
the same ``BEGIN IMMEDIATE`` transaction** as the state transition it
describes. Workers buffer payload *data* only (unhashed, unsequenced);
``seq``, ``prev_hash``, and ``entry_hash`` are computed here, against the
live chain tail — never ahead of time. Batch flushes are ≤ 500 entries, one
fsync each (case DB runs ``synchronous=FULL``).

``seq`` is commit order (E-09); wall-clock timestamps are advisory. Metrics
never enter the chain (§8b): entropy, confidence, and similar live in
artifact/triage tables; an audit entry references them by ID.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from specter.audit.chain import canonical, entry_hash, genesis

#: Soft cap per flush batch — one fsync amortized this way (§8c).
MAX_BATCH = 500


def utc_now_iso() -> str:
    """Current time as a UTC ISO-8601 string (advisory only; E-09)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class ChainReport:
    """Result of an O(n) chain walk."""

    ok: bool
    entries: int
    first_break_seq: int | None
    detail: str


def build_payload(
    *,
    seq: int,
    case_id: int,
    prev_hash: str,
    actor: str,
    actor_role: str,
    action: str,
    target: dict[str, Any] | None = None,
    config_snapshot: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Assemble the payload dict. Only ints/strs/bools/None may appear."""
    return {
        "seq": seq,
        "case_id": case_id,
        "prev_hash": prev_hash,
        "actor": actor,
        "actor_role": actor_role,
        "action": action,
        "target": target or {},
        "config": config_snapshot or {},
        "data": data or {},
        "ts": timestamp or utc_now_iso(),
    }


def append(
    conn: sqlite3.Connection,
    *,
    case_id: int,
    actor: str,
    actor_role: str,
    action: str,
    target: dict[str, Any] | None = None,
    config_snapshot: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
) -> str:
    """Append one entry for a case and return its hash.

    Must be called **inside the caller's transaction** — co-commitment means
    this entry and the transition it describes commit or roll back together.
    """
    tail = conn.execute(
        "SELECT seq, entry_hash FROM audit_entries WHERE case_id = ? ORDER BY seq DESC LIMIT 1",
        (case_id,),
    ).fetchone()
    seq = int(tail["seq"]) + 1 if tail else 1
    prev_hash = tail["entry_hash"] if tail else genesis(case_id)
    ts = utc_now_iso()

    payload = build_payload(
        seq=seq,
        case_id=case_id,
        prev_hash=prev_hash,
        actor=actor,
        actor_role=actor_role,
        action=action,
        target=target,
        config_snapshot=config_snapshot,
        data=data,
        timestamp=ts,
    )
    digest = entry_hash(payload)
    conn.execute(
        "INSERT INTO audit_entries (case_id, seq, prev_hash, payload, entry_hash, actor, actor_role, recorded_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (case_id, seq, prev_hash, canonical(payload), digest, actor, actor_role, ts),
    )
    return digest


def verify(conn: sqlite3.Connection, case_id: int) -> ChainReport:
    """Walk the chain for a case and verify it, O(n).

    Checks per entry: ``seq`` is contiguous from 1; ``prev_hash`` links to
    the previous entry (genesis for entry 1); ``entry_hash`` recomputes from
    the stored canonical payload. Returns the first break's seq if found.
    """
    rows = conn.execute(
        "SELECT seq, prev_hash, payload, entry_hash FROM audit_entries"
        " WHERE case_id = ? ORDER BY seq",
        (case_id,),
    ).fetchall()

    expected_prev = genesis(case_id)
    expected_seq = 1
    for row in rows:
        seq = int(row["seq"])
        if seq != expected_seq:
            return ChainReport(False, expected_seq - 1, seq, f"seq gap at {seq}")
        if row["prev_hash"] != expected_prev:
            return ChainReport(False, expected_seq - 1, seq, f"prev_hash mismatch at {seq}")
        payload = json.loads(row["payload"])
        if entry_hash(payload) != row["entry_hash"]:
            return ChainReport(False, expected_seq - 1, seq, f"entry_hash mismatch at {seq}")
        expected_prev = row["entry_hash"]
        expected_seq += 1
    return ChainReport(True, len(rows), None, "chain ok")