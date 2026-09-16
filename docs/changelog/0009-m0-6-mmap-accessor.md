# 0009 — M0-6 done: read-only mmap accessor (carve/mmap_accessor.py)

- **Date:** 2026-09-15
- **Type:** change
- **Spec refs:** §6 (read-only access, never writable), §13 (64-bit only,
  demand-paged mapping), §17 (zero-length images refused), P-02 (stat
  metadata captured at open)
- **Tag:** —

## Summary

Implemented the only door to an evidence image: `open_image()` maps a file
read-only (`PROT_READ` on POSIX, `ACCESS_READ` on Windows), refuses to run on
a 32-bit platform, and refuses zero-length files with a clear error. Every
open captures stat metadata (size, mtime_ns, inode) so a moved or replaced
image is caught cheaply before any re-hashing. The mapping is exposed via a
context-manager wrapper (`ReadOnlyImage`) so the caller can slice it directly.

## What changed

- `src/specter/carve/mmap_accessor.py` — full implementation (was a stub).
- `tests/unit/test_mmap_accessor.py` — 4 tests: bytes map correctly and
  slicing works; a write raises `TypeError` (never writable, §6); zero-length
  refused; missing path refused.
- `docs/TASKS.md` — M0-6 marked done; changelog 0009.

## Verification

Ran the accessor directly under Python 3.14: correct byte mapping, inode
captured, writes refused, zero-length refused. pytest tests will run in CI
(the local environment has no working virtualenv; CI is the matrix check).

## Next steps

- M0-7: `integrity/hashing.py` + `sidecar.py` — one-pass whole-image and
  chunk hashing, sidecar write, the unpadded trailing-chunk rule.