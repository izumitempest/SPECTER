"""Acquisition hashing — one sequential pass over the image (§6, §7.1, P-03).

A single read of the image computes both the whole-image SHA-256 and every
chunk hash. Hashing runs in C (OpenSSL via ``hashlib``) — no per-byte Python —
which is what makes the §9.5 target (≥ 200 MB/s) reachable.

Pinned rule (P-03): the trailing chunk is hashed at its **exact remaining
byte length, unpadded**; chunk count = ``ceil(size / chunk_size)``.
Acquisition and verification use the identical rule, so artifacts in the
final chunk verify like any other.

Usage::

    acquisition = hash_image(image.data, settings.chunk_size)
    write_sidecar(sidecar_path, acquisition.chunk_hashes)  # see sidecar.py
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Acquisition:
    """Result of the acquisition pass over one image."""

    whole_sha256: bytes
    chunk_hashes: tuple[bytes, ...]
    chunk_size: int
    size: int

    def chunk_count(self) -> int:
        """Number of chunks — equals ``ceil(size / chunk_size)`` (§7.1)."""
        return chunk_count(self.size, self.chunk_size)

    def hex_digest(self) -> str:
        """Whole-image hash as hex, for DB storage and display."""
        return self.whole_sha256.hex()


def chunk_count(size: int, chunk_size: int) -> int:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    return (size + chunk_size - 1) // chunk_size


def hash_image(data: bytes | bytearray | memoryview, chunk_size: int) -> Acquisition:
    """Hash ``data`` in one pass: whole-image SHA-256 + per-chunk hashes.

    ``data`` is anything supporting the buffer protocol (bytes, mmap, or a
    read-only memoryview). Views are used throughout so nothing per-byte
    reaches Python — only per-chunk hashing calls into OpenSSL.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    view = memoryview(data)
    size = len(view)

    whole = hashlib.sha256()
    chunks: list[bytes] = []
    for offset in range(0, size, chunk_size):
        block = view[offset : min(offset + chunk_size, size)]
        whole.update(block)
        chunks.append(hashlib.sha256(block).digest())
    return Acquisition(
        whole_sha256=whole.digest(),
        chunk_hashes=tuple(chunks),
        chunk_size=chunk_size,
        size=size,
    )