"""Acquisition hashing — one sequential pass over the image (§6 step 2, §7.1).

Computes the whole-image SHA-256 and every chunk hash in a single read of the
data. Hashing is the throughput-bound stage: the spec targets ≥ 200 MB/s cold
on the reference laptop (§9.5). SHA-256 runs in C (OpenSSL via ``hashlib``),
so per-byte work stays out of Python (§5).

Pinned rule (P-03): the trailing chunk is hashed at its **exact remaining
byte length, unpadded**. Chunk count = ``ceil(size / chunk_size)``.

Tasks: M0-7.
"""

from __future__ import annotations


def hash_image(data: memoryview, chunk_size: int) -> tuple[bytes, list[bytes]]:
    """Return ``(whole_sha256, chunk_hashes)`` in one pass (M0-7).

    Not yet implemented.
    """
    raise NotImplementedError("M0-7: hash_image")