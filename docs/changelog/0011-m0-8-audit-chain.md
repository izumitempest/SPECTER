# 0011 — M0-8 done: hash-chained audit log (chain + writer)

- **Date:** 2026-09-15
- **Type:** change
- **Spec refs:** §8a (canonical serialization), §8c (co-commitment), §16.3
  (tamper suite), P-04, E-09
- **Tag:** —

## Summary

Implemented the audit log's two halves. `chain.py` is the pure math: the
pinned canonical serialization (sorted keys, minimal separators, no floats —
rejected with a clear error), per-case genesis (`SHA256("specter-genesis:" +
case_id)`), and the `specter-audit-v1:` domain-tagged entry hash. `writer.py`
is the single write path: `append()` reads the case's live tail, computes
`seq` / `prev_hash` / `entry_hash`, and inserts the entry **inside the
caller's transaction** — co-commitment, so an entry and the state change it
describes commit or roll back together. `verify()` walks the chain O(n),
checking seq contiguity, prev-hash linkage, and hash recomputation.

## What changed

- `src/specter/audit/chain.py` — canonical/entry-hash/genesis + payload
  validator (floats rejected). Stub replaced.
- `src/specter/audit/writer.py` — `append()` (co-commitment), `verify()`
  returning a `ChainReport`, `build_payload()` helper, `utc_now_iso()`. Stub
  replaced.
- `tests/unit/test_audit.py` — 12 tests, including the tamper-suite boundary
  cases: interior edit breaks at that seq; mid-chain delete breaks; suffix
  delete verifies clean **by design** (the manifest checkpoint is what
  catches it, per §16.3 — the test says so).
- `docs/TASKS.md`, `docs/changelog/` — updated.

## Verification

Manual run: 3-entry chain verified OK; tampering entry 2 breaks verification
at seq 2; float payloads raise `PayloadError`. The hash formula matches the
spec byte-for-byte (computed independently and compared). CI runs the rest.

## Next steps

- M0-9 + M0-10: the scanner (windowed pass, cursor, alignment filter) and the
  JPEG/PNG structural parsers — the carving core.