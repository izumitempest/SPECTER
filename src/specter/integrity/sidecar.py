"""Chunk hash sidecar — the ``<image_id>.chunks`` file (§7.1, P-03).

The sidecar is a flat array of 32-byte SHA-256 values in chunk order, written
once during the acquisition pass:

    chunk_hash(i) = sidecar_bytes[i * 32 : (i + 1) * 32]

The database stores only the sidecar path, the chunk size, and the Merkle
root — no per-chunk rows. The DB's optional ``chunks_file_sha256`` gives the
sidecar a self-check that doesn't require the image.

Written atomically (temp file → ``os.replace``), matching the write protocol
used everywhere else in the codebase (§4.1).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

HASH_BYTES = 32  # SHA-256


def write_sidecar(path: str | Path, chunk_hashes: tuple[bytes, ...] | list[bytes]) -> Path:
    """Write the flat sidecar atomically; returns the final path."""
    path = Path(path)
    blob = b"".join(chunk_hashes)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(blob)
    os.replace(tmp, path)
    return path


def read_sidecar(path: str | Path) -> bytes:
    """Read the whole sidecar. Layout is 32 bytes per chunk, in order."""
    return Path(path).read_bytes()


def leaf_at(sidecar: bytes, index: int) -> bytes:
    """Chunk hash ``index`` — O(1) by construction: ``[index*32, +32)``."""
    if index < 0:
        raise IndexError(index)
    leaf = sidecar[index * HASH_BYTES : (index + 1) * HASH_BYTES]
    if len(leaf) != HASH_BYTES:
        raise IndexError(f"chunk index {index} out of range")
    return leaf


def count(sidecar: bytes) -> int:
    """Number of chunk hashes in a sidecar blob."""
    n, rem = divmod(len(sidecar), HASH_BYTES)
    if rem:
        raise ValueError("sidecar length is not a multiple of 32 bytes")
    return n


def self_check(path: str | Path, expected_sha256: str) -> bool:
    """Optional integrity self-check (the ``chunks_file_sha256`` column)."""
    return hashlib.sha256(read_sidecar(path)).hexdigest() == expected_sha256