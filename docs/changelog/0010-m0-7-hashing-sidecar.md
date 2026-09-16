# 0010 — M0-7 done: acquisition hashing + chunk sidecar

- **Date:** 2026-09-15
- **Type:** change
- **Spec refs:** §6 step 2 (single pass), §7.1 (sidecar layout), P-03
  (partial trailing chunk; optional `chunks_file_sha256`)
- **Tag:** —

## Summary

Implemented the acquisition path. `hash_image()` walks the image exactly
once, feeding every chunk buffer to two SHA-256 hashes (whole-image and
per-chunk) — no double read, no per-byte Python, so the §9.5 throughput
target (≥ 200 MB/s) stays reachable. The trailing-chunk rule is pinned: the
last chunk is hashed at its **exact remaining byte length, unpadded**, and
the chunk count is always `ceil(size / chunk_size)`. The sidecar module
writes `<image_id>.chunks` as one flat 32-byte-per-record file (atomic
temp→rename), with `leaf_at(i)` giving O(1) leaf reads and `self_check()`
backing the optional `chunks_file_sha256`.

## What changed

- `src/specter/integrity/hashing.py` — `Acquisition` dataclass,
  `chunk_count()`, `hash_image()`. Stub replaced.
- `src/specter/integrity/sidecar.py` — `write_sidecar`, `read_sidecar`,
  `leaf_at`, `count`, `self_check`; HASH_BYTES = 32 documented.
- `tests/unit/test_integrity.py` — 13 tests: whole-image hash matches
  `hashlib.sha256`; the P-03 partial trailing chunk is unpadded and exactly
  `sha256(last_n_bytes)`; chunk count is `ceil(size / chunk_size)`; chunk
  hashes are independent and ordering-stable; determinism; buffer-protocol
  input (memoryview) accepted; sidecar round-trip, O(1) leaf lookup, out-of-
  range index raises IndexError, malformed (non-32-multiple) length raises
  ValueError, self-check pass/fail, atomic write leaves no `.tmp`.
- `docs/TASKS.md` — M0-7 marked done; changelog 0010.

## Verification

Ran both modules against a 100 KB synthetic buffer (chunk_size = 256) under
Python 3.14: whole hash = `sha256(data)`, 391 chunks, trailing chunk hash =
`sha256` of the last 100000 mod 256 = 144 bytes, sidecar self-check passes.
CI runs the pytest suite.

## Next steps

- M0-8: `audit/` — canonical serialization, genesis, co-commitment append,
  O(n) verify. Then the scanner skeleton (M0-9) closes the M0 core loop.