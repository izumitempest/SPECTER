"""Audit chain — canonical serialization, genesis, entry hashing (§8a–b).

Pinned rules (V3.3 §8):

- **Serialization** is exactly::

    json.dumps(payload, sort_keys=True, separators=(",", ":"),
               ensure_ascii=True, allow_nan=False)

  hashed as ``SHA256(b"specter-audit-v1:" + canonical.encode("utf-8"))``.
  The verification path calls this same function; nothing else serializes
  payloads.
- **No floats** anywhere in a payload — integers, strings, booleans, null
  only; timestamps are UTC ISO-8601 strings, sizes are integers (P-04b).
  Rejected at write time, so a bad entry can never enter the chain.
- **Genesis** for a case is ``SHA256(b"specter-genesis:" + str(case_id))``.
- ``seq`` is commit order (E-09): a chronological log of committed
  transitions. Concurrent jobs interleave in commit order, by design.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

CHAIN_TAG = b"specter-audit-v1:"


class PayloadError(ValueError):
    """Payload contains a forbidden type (e.g. a float) or isn't JSON."""


def genesis(case_id: int | str) -> str:
    """The chain's starting prev_hash for a case."""
    return hashlib.sha256(b"specter-genesis:" + str(case_id).encode()).hexdigest()


def _validate_node(value: Any, path: str) -> None:
    """Reject anything but int/str/bool/None (and containers of them)."""
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        raise PayloadError(f"{path}: floats are forbidden in audit payloads (§8b)")
    if isinstance(value, dict):
        for key, child in value.items():
            _validate_node(child, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_node(child, f"{path}[{index}]")
        return
    raise PayloadError(f"{path}: unsupported type {type(value).__name__}")


def canonical(payload: dict[str, Any]) -> str:
    """The canonical JSON string for a payload. The only serializer."""
    _validate_node(payload, "$")
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def entry_hash(payload: dict[str, Any]) -> str:
    """SHA-256 of the domain tag + canonical payload. Pinned by §8a."""
    return hashlib.sha256(CHAIN_TAG + canonical(payload).encode("utf-8")).hexdigest()