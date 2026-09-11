# SPECTER Implementation Plan

This document explains **how** we build SPECTER: the order of work, the rules
that must never be broken, the conventions to follow, and how testing works.
For **what** to build and its current status, see `docs/TASKS.md`. For the
frozen design itself, see `PROJECT.md` (spec v3.3).

## 1. Reading order

- `PROJECT.md` — the frozen spec (v3.3). It is final; changes to it go through
  the `spec-errata` process (§0), never direct edits.
- `docs/TASKS.md` — the live task list with statuses.
- This file — how to build it.
- `docs/spec/` — pre-merge history (why each decision was made); consult when
  a design choice looks surprising.

## 2. Build order (and why)

We build bottom-up, CLI-first:

1. **M0 core** — config → database → mmap accessor → hashing/sidecar → audit
   chain → scanner skeleton (JPEG + PNG only) → jobs → CLI vertical slice
   (`init → image → hash → carve → list`).
   *Why first:* every later milestone consumes these pieces; a CLI slice makes
   each of them testable headless before any UI exists.
2. **M1 carving breadth** — the remaining seven format parsers, the defensive
   parsing rules, the three test corpora, and the two performance gates
   (§9.5 throughput, P-09 density). The gates run at **week 4–5**, because
   failure there forces architectural change (§5 escape hatches).
3. **M2 integrity + audit** — Merkle proofs, manifest, co-committed audit in
   workers, blob GC, kill test. Built after carving because the proof
   endpoint verifies *artifact* ranges (§7.2).
4. **M3 triage** — entropy, keyword search, known-file sets, loose-file
   import. Threshold derivation needs the labeled corpus from M3-3.
5. **M4 API + UI** — FastAPI + server-rendered Jinja2. Last-but-one on
   purpose: it adds surface, not science.
6. **M5–M6** — evaluation, packaging, thesis.

## 3. Global invariants — the rules that must never regress

Every review and every new module is checked against this list:

1. **Per-byte work stays in C.** Python runs per candidate match and per
   artifact — never per byte of the image (§5).
2. **Parsers are total:** never raise, never hang; malformed input degrades
   to a recovery-or-rejection with a confidence flag (§9.3).
3. **O(1) rejection** before any cap-sized scan (P-07).
4. **Windows bound the scan, never the parsers.** The 64-byte overlap is
   never raised to the safety cap (P-05).
5. **One cursor per carve job; the scan loop is sequential** in one worker
   (P-08, E-06).
6. **Deduplicate bytes, never records** (P-08).
7. **Audit:** no floats in payloads; serialization is single-sourced; a state
   transition and its entry commit in one transaction; `seq` is commit order
   (P-04, E-09).
8. **Chunk hashing:** the trailing chunk is hashed unpadded, at its exact
   remaining length (P-03).
9. **Merkle:** the pinned construction — fixed-width concatenation, odd nodes
   duplicated, a lone leaf is its own root (E-03).
10. **Read-only access to images — always** (§6).
11. **Blob writes:** temp file → commit → rename; readers never repair; GC is
    two-phase (E-02, E-04).
12. **Artifacts are never rendered as their native type** in the browser
    (§11).
13. **Cross-case access returns 404, not 403; authorization runs before any
    file handle opens** (P-12).
14. **Single API process** (E-07).
15. **Path containment** via `realpath` + commonpath at serve time (§12).

## 4. Module-by-module notes

| Module | Core of the work | Watch out for |
| --- | --- | --- |
| `config.py` | env resolution order: defaults → `.env` → environment; production fail-fast | placeholder secrets in production (§12) |
| `db.py` | schema v1 (11 tables), WAL + busy_timeout, `schema_version` migrations | no `chunks` table — hashes live in the sidecar (P-03) |
| `carve/mmap_accessor.py` | read-only whole-file mmap, POSIX/Windows, 64-bit guard | 32-bit must be refused, and re-verify stat metadata at open (P-02) |
| `carve/scanner.py` | windows (128 MiB, 64 B overlap), alignment filter, cursor, masking counter | overlap is fixed; cursor skips recovered *and attempted* regions |
| `carve/signatures.py` | registry of the 9 types | O(1) rejection first (P-07); table version is audited |
| `carve/formats/jpeg.py` | the two-mode state machine — hardest parser | E-01 fill bytes, E-01+ dangling FF, progressive re-entry; fixtures via cjpeg recipes |
| `carve/formats/*` | GIF, PDF, ZIP, PE, SQLite, BMP, MP4 per §9.2 | every §9.2 edge case gets a golden fixture |
| `integrity/hashing.py` | one pass: whole-image SHA-256 + chunks | the unpadded partial trailing chunk rule |
| `integrity/sidecar.py` | flat 32-byte array, O(1) leaf lookup | optional `chunks_file_sha256` self-check |
| `integrity/merkle.py` | pinned tree (E-03), proofs, verify | a 1-leaf tree's root is the leaf itself |
| `integrity/manifest.py` | export/verify; audit-head checkpoint | the honest-limits text goes in the writeup, not just code |
| `audit/chain.py` | pinned serialization (§8a), genesis, O(n) verify | verification calls the exact same serializer |
| `audit/writer.py` | co-commitment flush; ≤500-entry batches | metrics never enter the chain (P-04b) |
| `triage/entropy.py` | pinned `block_entropy`; per-type position windows | stored aggregated (§4.1.4); never whole-image |
| `triage/search.py` | 1 MiB slices; `bytes.find` literals; regex clamp with truncation flags | unbounded patterns are clamped, not rejected (E-05) |
| `triage/known.py` | sorted-array binary search (+ Bloom); confirm before tagging | the false-known error is the harmful one |
| `jobs/manager.py` | job table, per-image lock, disk pre-flight, `paused_disk` | re-runs must be idempotent (§4) |
| `store/blob.py` | temp → commit → rename; reader retry 5×20 ms | readers never repair — GC does |
| `store/gc.py` | two-phase delete, ≤256 unlinks per pass | Windows `PermissionError` vs POSIX `ENOENT` handled by skipping |
| `api/*` | app factory, JWT cookie auth, `require_case_access` | 404 (not 403) cross-case; role recorded in audit |
| `ui/` | Jinja2 templates, hex viewer, ≤300 lines JS | octet-stream only for carved bytes |

## 5. Testing, operationalised (§17)

- **Unit / golden** (`tests/unit`, `tests/golden/fixtures`): one fixture per
  format edge case, scored byte-exact.
- **Property** (`tests/property`, Hypothesis): Merkle mutation, chain
  mutation, suffix deletion, O(1) rejection, regex boundary-spanning.
- **Fuzz** (`tests/fuzz`): random bytes and *mutated valid fixtures*. The
  mutated corpus doubles as the P-09 density corpus. Parsers must never
  raise or hang.
- **Kill test** (`tests/unit/test_kill.py`): SIGKILL a worker mid-carve, then
  assert the four crash-consistency conditions (committed rows only, E-08).
- **Benchmarks** (`tests/benchmarks`): §9.5 throughput (cold + warm) and the
  P-09 density sweep; results committed as JSON.
- **Determinism regression:** the same image carved twice yields an identical
  artifact list.
- **CI** runs `pytest -m "not slow and not bench"` on Linux + Windows, plus
  ruff and mypy.

## 6. Conventions

- Python ≥ 3.11, `from __future__ import annotations`, mypy strict, ruff for
  lint/format. Run ruff before pushing — CI gates on it.
- Naming: the SQLite format parser is `sqlite_fmt.py` (never `sqlite.py`,
  to stay clear of the stdlib import).
- Sizes are integers; timestamps are UTC ISO-8601 strings; confidence in
  audit payloads is basis points or pinned-precision strings (never floats).
- Ranges are half-open: `[offset, offset + length)`.
- Every material change ships with a `docs/changelog/NNNN-*.md` entry and an
  index row — in the same commit.

## 7. Developer workflow

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
specter --help                      # CLI boots
pytest -m "not slow and not bench"  # the CI test set
pytest -m property                  # Hypothesis only
ruff check . && mypy src            # before every commit
```

The first lab exercise a student performs — adding the RAR signature — is
also the canonical "add a parser" walkthrough: registry entry in
`signatures.py`, parser module in `formats/`, golden fixture, O(1)-rejection
check, changelog entry.

## 8. The gates

The only items that can force an architectural change this late:

1. **§9.5 throughput** (≥ 150 MB/s scan, ≥ 200 MB/s hashing, 16 GB in
   ≤ 30 min) — measured in M1.
2. **P-09 density gate** (≥ 50% of clean throughput at 10⁴ candidates/GB) —
   measured at week 4–5, *not* week 8.

Both failed-to-met triggers open the escape hatches in §5. Everything else
degrades via the §18 drop order.