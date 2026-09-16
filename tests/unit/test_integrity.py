"""Tests for M0-7: acquisition hashing + chunk sidecar (§7.1, P-03)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from specter.integrity.hashing import Acquisition, chunk_count, hash_image
from specter.integrity.sidecar import (
    HASH_BYTES,
    count,
    leaf_at,
    read_sidecar,
    self_check,
    write_sidecar,
)


class TestChunkCount:
    def test_exact_multiple(self) -> None:
        assert chunk_count(1024, 256) == 4

    def test_partial_trailing_chunk(self) -> None:
        # P-03: ceil(size / chunk_size), trailing chunk kept at its real size.
        assert chunk_count(1025, 256) == 5
        assert chunk_count(1, 4 * 1024 * 1024) == 1

    def test_rejects_zero_chunk_size(self) -> None:
        with pytest.raises(ValueError):
            chunk_count(100, 0)


class TestHashImage:
    def test_whole_hash_matches_sha256(self) -> None:
        data = bytes(range(256)) * 3
        acq = hash_image(data, chunk_size=128)
        assert acq.whole_sha256 == hashlib.sha256(data).digest()
        assert acq.size == len(data)

    def test_partial_trailing_chunk_unpadded(self) -> None:
        # P-03 golden rule: image size not divisible by chunk size.
        data = b"A" * 100
        acq = hash_image(data, chunk_size=32)
        # 4 chunks: 3 full (96 bytes) + 1 partial (4 bytes).
        assert acq.chunk_count() == 4
        assert acq.chunk_hashes[-1] == hashlib.sha256(b"A" * 4).digest()
        assert acq.chunk_hashes[0] == hashlib.sha256(b"A" * 32).digest()

    def test_chunk_hashes_independent_of_whole(self) -> None:
        data = b"abcdefghij" * 7
        acq = hash_image(data, chunk_size=10)
        rebuilt = b"".join(
            hashlib.sha256(data[i : i + 10]).digest() for i in range(0, 70, 10)
        )
        assert b"".join(acq.chunk_hashes) == rebuilt

    def test_deterministic(self) -> None:
        data = bytes(range(256))
        first = hash_image(data, chunk_size=64)
        second = hash_image(data, chunk_size=64)
        assert first == second

    def test_accepts_memoryview(self) -> None:
        data = b"viewed" * 16
        acq = hash_image(memoryview(bytearray(data)), chunk_size=8)
        assert len(acq.chunk_hashes) == chunk_count(len(data), 8)


class TestSidecar:
    def _acq(self) -> Acquisition:
        return hash_image(bytes(range(64)), chunk_size=16)

    def test_round_trip_and_o1_leaf(self, tmp_path: Path) -> None:
        acq = self._acq()
        path = write_sidecar(tmp_path / "img-1.chunks", list(acq.chunk_hashes))
        raw = read_sidecar(path)
        assert len(raw) == len(acq.chunk_hashes) * HASH_BYTES
        assert count(raw) == 4
        assert leaf_at(raw, 0) == acq.chunk_hashes[0]
        assert leaf_at(raw, 3) == acq.chunk_hashes[-1]

    def test_leaf_out_of_range(self) -> None:
        with pytest.raises(IndexError):
            leaf_at(self._acq_sidecar_bytes(), 4)

    def _acq_sidecar_bytes(self) -> bytes:
        return b"".join(self._acq().chunk_hashes)

    def test_bad_length_sidecar_refused(self) -> None:
        with pytest.raises(ValueError, match="multiple of 32"):
            count(b"\x00" * 33)

    def test_self_check(self, tmp_path: Path) -> None:
        acq = self._acq()
        path = write_sidecar(tmp_path / "img-1.chunks", list(acq.chunk_hashes))
        digest = hashlib.sha256(read_sidecar(path)).hexdigest()
        assert self_check(path, digest)
        assert not self_check(path, "0" * 64)

    def test_write_is_atomic(self, tmp_path: Path) -> None:
        # The final path exists and no leftover .tmp file remains.
        acq = self._acq()
        path = write_sidecar(tmp_path / "img-1.chunks", list(acq.chunk_hashes))
        assert path.exists()
        assert not (tmp_path / "img-1.chunks.tmp").exists()