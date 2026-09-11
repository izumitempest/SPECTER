# SPECTER Task List

The authoritative task list, aligned to `PROJECT.md` §18 (milestones M0–M6
with exit criteria). Task statuses are updated in the same commit as the work
they track, and every material change also gets a changelog entry
(`docs/changelog/`, policy CX-1).

**Status legend:** `[ ]` pending · `[~]` in progress · `[x]` done.

Tasks reference spec sections and patch/errata IDs (P-xx, E-xx). The spec is
frozen at v3.3 — new findings go to the issue tracker as `spec-errata`, not
into the spec (§0). The drop order for behind-schedule cuts is defined in §18.

---

## M0 — Baseline + vertical slice (weeks 1–3)

**Exit:** repo, CI, security baseline; CLI: image → hash → carve → list.

| ID | Task | Spec | Status |
| --- | --- | --- | --- |
| M0-1 | Repo init (git, main branch) and import of the three spec documents | §0 | [x] |
| M0-2 | Merge P-01…P-18 + ERRATA-001 into PROJECT.md, tag `spec-v3.3` | §0 | [x] |
| M0-3 | Scaffold: packaging, CI, source tree, module stubs, changelog practice | App A, §4 | [x] |
| M0-4 | `config.py`: env loading, `.env.example`, production fail-fast on placeholders | §12 | [ ] |
| M0-5 | `db.py`: schema v1 (11 tables), WAL + busy_timeout, `schema_version` bootstrap | §15, §4 | [ ] |
| M0-6 | `mmap_accessor`: POSIX `PROT_READ` / Windows `ACCESS_READ`, 64-bit guard | §6, §9.1, §13 | [ ] |
| M0-7 | `hashing.py` + `sidecar.py`: single-pass whole-image + chunk hashing, sidecar write, partial-trailing-chunk rule | §6.2, §7.1, P-03 | [ ] |
| M0-8 | `audit`: pinned canonical serialization, genesis, co-committed append, O(n) verify | §8, P-04 | [ ] |
| M0-9 | Scanner skeleton: windowed pass (128 MiB, 64 B overlap), alignment filter, safety cap, cursor, signature registry | §9.1, §9.3, §9.4, P-05/P-07/P-08 | [ ] |
| M0-10 | Formats MVP: JPEG + PNG minimal structural, golden fixtures (uniform JPEG, EXIF-thumbnail JPEG, bad-CRC PNG) | §9.2, §17 | [ ] |
| M0-11 | Jobs: manager (job table, per-image lock) + pool (ProcessPoolExecutor) | §4, §4.1.1, E-06 | [ ] |
| M0-12 | CLI vertical slice: `init` / `image add` / `hash` / `carve` / `list` | §18 M0, §6 | [ ] |
| M0-13 | Security baseline wiring: argon2id helper (pinned params), JWT keyfile bootstrap in `specter init` | §12, P-12 | [ ] |
| M0-14 | Determinism: same image → identical artifact list (golden regression); smoke tests green on CI (Linux + Windows) | §17, §16.7 | [ ] |

## M1 — Carving engine (weeks 4–8)

**Exit (P-18):** all nine types structural *or* demoted per the drop order,
with demoted fallbacks passing the same golden tests; §9.5 throughput targets
met *or* the optimization branch opened; density gate run at week 4–5 (P-09).

| ID | Task | Spec | Status |
| --- | --- | --- | --- |
| M1-1 | GIF + ZIP parsers (local-header walk, EOCD fallback) + golden fixtures | §9.2, P-06 | [ ] |
| M1-2 | PDF (last %%EOF), EXE/PE (e_lfanew + PE\\0\\0), SQLite (page math), BMP (clamp), MP4 (box chain 0/1) | §9.2, §9.3 | [ ] |
| M1-3 | JPEG state machine: marker/entropy modes, E-01 fill bytes, E-01+ dangling FF; committed cjpeg recipes (baseline/-restart/-progressive) | §9.2, P-06, E-01/E-01+/E-10, §17 | [ ] |
| M1-4 | Defensive parsing: O(1) rejection rule (P-07) enforced by property tests; totality fuzz harness | §9.3, P-07, P-17 | [ ] |
| M1-5 | Cursor semantics: recovered *and* attempted regions skipped, cross-type nesting suppression, masking-rate counter | §9.4, P-08, E-06 | [ ] |
| M1-6 | Blob writer path: temp → commit → rename, materialization check, reader retry (5 × 20 ms) | §4.1.2, E-04/E-04+ | [ ] |
| M1-7 | Corpora C1 (synthetic contiguous) + C2 (mtools FAT32, populate-then-delete), seeded scripts; golden scoring harness | §16.1 | [ ] |
| M1-8 | Corpus C3 (adversarial list) + mutation fuzzer (P-17) — doubles as the P-09 density corpus | §16.1, §17, P-17 | [ ] |
| M1-9 | Throughput benchmark: §9.5 targets on reference hardware, cold/warm methodology, results as JSON | §9.5, §16.1 | [ ] |
| M1-10 | Density gate: 10³–10⁵ candidates/GB sweep, ≥ 50% of clean throughput at 10⁴/GB | §9.5, P-09 | [ ] |

## M2 — Integrity + audit (weeks 9–12)

**Exit:** sidecar, tree, proofs, manifest export/verify, chain, property
tests, kill test.

| ID | Task | Spec | Status |
| --- | --- | --- | --- |
| M2-1 | `merkle.py`: pinned construction (odd-node duplication, fixed-width concat, n=1 rule); fixtures (odd count, partial trailing chunk, sub-chunk image) | §7.1, E-03 | [ ] |
| M2-2 | Sidecar verify + optional `chunks_file_sha256` self-check | §7.1, P-03 | [ ] |
| M2-3 | Proof verification (§7.2): re-read range hash + covering-chunk Merkle proofs | §7.2 | [ ] |
| M2-4 | `manifest.py`: export (roots, audit head + seq, tool version, UTC) + verify; audit-head checkpoint every export | §7.3, §8 | [ ] |
| M2-5 | Co-commitment in workers: flush batch = artifact/blob rows + entries in one `BEGIN IMMEDIATE`; ≤500-entry batch, `synchronous=FULL` | §8(c), P-04c | [ ] |
| M2-6 | Job lifecycle: statuses, idempotent re-run, failed marking, disk pre-flight + `paused_disk`, per-image lock | §4, §4.1.1/4.1.3 | [ ] |
| M2-7 | GC: two-phase (E-02), ≤256 unlinks/pass, reconciliation both directions, temp sweep, summary audit entry | §4.1.5, E-02/E-02+ | [ ] |
| M2-8 | Kill test: SIGKILL mid-carve on a deterministic corpus, four assertions (committed rows only) | §17, P-17, E-08 | [ ] |
| M2-9 | Property tests: Merkle mutation → proof fails; chain interior edit → break; suffix deletion → detected to last manifest | §16.3, §17 | [ ] |

## M3 — Triage (weeks 13–16)

**Exit:** type-aware entropy, keyword search, dedupe, loose-file import,
hash sets.

| ID | Task | Spec | Status |
| --- | --- | --- | --- |
| M3-1 | `entropy.py`: pinned `block_entropy`, 4 KiB blocks, aggregated profile storage (head/tail/majority + histogram) | §10.1, §4.1.4 | [ ] |
| M3-2 | Position windows (P-10): tail-window low-entropy truncated flag per type | §10.1, P-10 | [ ] |
| M3-3 | Labeled corpus (encrypted, compressed-not-encrypted, plaintext, UPX, truncated) + threshold derivation + ROC/AUC harness with bootstrap CIs | §16.2, P-14 | [ ] |
| M3-4 | `search.py`: 1 MiB streaming; literals via `bytes.find`; regex computed-overlap + clamp (64 KiB, truncation flag); boundary-spanning property tests | §10.3, P-11, E-05 | [ ] |
| M3-5 | `known.py`: NSRL CSV → sorted binary array (+ optional Bloom), confirm-before-tag | §10.3, P-11 | [ ] |
| M3-6 | Loose-file import: signature/extension mismatch, OOXML `[Content_Types].xml` refinement | §10.2 | [ ] |
| M3-7 | `TriageFinding` rows + surfacing in CLI/API | §10.3, §15 | [ ] |

## M4 — API + UI (weeks 17–20)

**Exit:** server-rendered UI, hex viewer, roles, audit view.

| ID | Task | Spec | Status |
| --- | --- | --- | --- |
| M4-1 | `api/app.py`: factory, config, middleware (CSP); single-API-process constraint | §12, §13, E-07 | [ ] |
| M4-2 | `api/auth.py`: JWT httponly cookie + `SameSite=Lax`, double-submit CSRF, argon2id, 8 h TTL, token-bucket rate limit | §12, P-12 | [ ] |
| M4-3 | `api/deps.py`: `require_case_access` (membership or admin before file handles; 404 not 403; actor role in audit) | §12, P-12 | [ ] |
| M4-4 | Endpoints: case CRUD, image register (by-path + verified copy), job submit/status, artifact list/serve-by-ID (containment), hex byte-range, chain verify, manifest export | §6, §11, §12 | [ ] |
| M4-5 | `ui`: Jinja2 templates (dashboard, case, triage, hex viewer 256 B pages, audit trail + verify button, manifest export); ≤300 lines JS; octet-stream only | §11 | [ ] |
| M4-6 | E2E smoke (httpx): create case → register → carve → verify chain → export manifest | §11, §12 | [ ] |

## M5 — Evaluation (weeks 21–24)

**Exit:** all §16 suites run, results committed.

| ID | Task | Spec | Status |
| --- | --- | --- | --- |
| M5-1 | §16.1 carve benchmark C1–C3: recall/precision/completeness/throughput/masking rate, cold + warm | §16.1, §9.4 | [ ] |
| M5-2 | §16.2 ROC/AUC + bootstrap CIs + per-class counts | §16.2, P-14 | [ ] |
| M5-3 | §16.3 tamper suite (image flip, leaf, proof, manifest; chain edit; suffix delete) | §16.3 | [ ] |
| M5-4 | §16.4 PhotoRec + Autopsy comparison, workload disclosure, packaging parity (onedir) | §16.4, P-15 | [ ] |
| M5-5 | §16.5 teaching study (recruit at M2) + timeboxed PhotoRec C control condition | §16.5, P-16 | [ ] |
| M5-6 | §16.6 offline run + user study; §16.7 reproducibility bundle (pins, seeds, results JSON) | §16.6–16.7 | [ ] |

## M6 — Packaging + writeup (weeks 25–28)

**Exit:** packaged install, thesis, buffer.

| ID | Task | Spec | Status |
| --- | --- | --- | --- |
| M6-1 | Packaging: pip install from sdist verified; PyInstaller onedir parity (never onefile) | §13, P-15 | [ ] |
| M6-2 | `docs/TOUR.md` module map + 4 labs (RAR signature, break Merkle proof, chain break, entropy profile) + solutions branch | §11.4, §16.5 | [ ] |
| M6-3 | Thesis + final README + ethics statement | §19 | [ ] |
| M6-4 | Final regression (all suites), results committed, first release tag | §17, §18 | [ ] |

## Cross-cutting (CX) — ongoing

| ID | Task | Spec | Status |
| --- | --- | --- | --- |
| CX-1 | Changelog discipline: every material change gets a numbered, dated entry in `docs/changelog/` in the same commit | project policy | [x] |
| CX-2 | Spec-errata process: findings → issues labeled `spec-errata`, citing patch IDs | §0 | [ ] |
| CX-3 | Dependency pinning + reproducible environment (lockfile/constraints) | §16.7 | [ ] |
| CX-4 | Security review against the §12 checklist at each milestone | §12 | [ ] |

## Recruiting note

Student-study participants are recruited **at M2**, not M5 (§18 risk
register — recruit early, peers as fallback), because the study is the
evidence for the project's primary claim (§16.5).