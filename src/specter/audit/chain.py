"""Audit chain — canonical serialization, genesis, verification (§8).

The entry hash is pinned (§8a):

    entry_hash = SHA256(b"specter-audit-v1:" + json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False).encode("utf-8"))

Rules that keep the chain sound:

- **No floats.** Payloads are integers, strings, booleans, and null only.
  Timestamps are ISO-8601 strings; sizes are integers (P-04b).
- **Genesis** for a case is ``SHA256(b"specter-genesis:" + case_id)``.
- **seq is commit order** — a chronological log of committed transitions,
  not spatial order (E-09). Evidence order lives in artifact offsets.
- **Verification** walks the chain O(n): each entry's ``prev_hash`` must
  match the previous entry's hash, and each ``entry_hash`` must recompute.

Tasks: M0-8 (serialize/hash/verify), M2-9 (property tests for chain breaks).
"""

from __future__ import annotations


def entry_hash(payload: dict[str, object]) -> str:
    """Compute the pinned entry hash for a canonical payload (M0-8).

    Not yet implemented.
    """
    raise NotImplementedError("M0-8: entry_hash")