"""Chunk hash sidecar — ``<image_id>.chunks`` (§7.1, P-03).

The sidecar is a flat array of 32-byte SHA-256 values, written sequentially
during the acquisition pass: ``chunk_hash(i) = bytes[i*32 : (i+1)*32]``. The
database stores only the sidecar path, the chunk size, and the Merkle root —
no per-chunk rows.

Why a flat file instead of a chunks table: O(1) leaf lookup, sequential
write, zero index machinery, and a format that is trivial to audit. Its
integrity is committed by the Merkle root, and an optional
``chunks_file_sha256`` lets the sidecar self-check without the image.

Tasks: M0-7 (write), M2-2 (verify + self-check).
"""

from __future__ import annotations


def leaf_at(hashes: bytes, index: int) -> bytes:
    """Return chunk hash ``index`` (32 bytes at ``index * 32``)."""
    return hashes[index * 32 : (index + 1) * 32]