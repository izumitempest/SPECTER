"""Security baseline helpers (M0-13; §12, P-12).

This is the M0 slice of the auth storey: argon2id password hashing with the
pinned cost parameters, and the JWT keyfile bootstrap used by `specter init`.
The full cookie/CSRF endpoint work lands in `specter/api/auth.py` at M4-2 —
this module is the shared, separately testable piece both build on.
"""

from __future__ import annotations

import secrets
from pathlib import Path

#: Pinned argon2id parameters (P-12): memory in KiB, iterations, parallelism.
ARGON2_MEMORY_COST_KIB = 65536
ARGON2_TIME_COST = 3
ARGON2_PARALLELISM = 1


def hash_password(password: str) -> str:
    """Hash a password with argon2id at the pinned parameters."""
    import argon2  # local import: CLI-only tools shouldn't require it

    from argon2 import PasswordHasher

    ph = PasswordHasher(
        memory_cost=ARGON2_MEMORY_COST_KIB,
        time_cost=ARGON2_TIME_COST,
        parallelism=ARGON2_PARALLELISM,
    )
    return ph.hash(password)


def verify_password(stored_hash: str, candidate: str) -> bool:
    """Constant-time check; returns False on mismatch or invalid hash."""
    from argon2 import PasswordHasher
    from argon2.exceptions import InvalidHash, VerificationError

    ph = PasswordHasher(
        memory_cost=ARGON2_MEMORY_COST_KIB,
        time_cost=ARGON2_TIME_COST,
        parallelism=ARGON2_PARALLELISM,
    )
    try:
        return bool(ph.verify(stored_hash, candidate))
    except (VerificationError, InvalidHash):
        return False


def write_jwt_keyfile(path: str | Path) -> Path:
    """Create the JWT keyfile (random 256-bit secret, 0600). No-op if it
    already exists — the deployment secret must survive restarts (P-12)."""
    path = Path(path)
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(secrets.token_bytes(32))
    path.chmod(0o600)
    return path