# SPECTER — Offline Forensic Triage Platform (Rebuild Spec, v3)

**Final Year Project Documentation** — Godfrey Okoye University, Enugu, Department of Computer Science.

Author: Okwuchukwu Ekene Don Davies.

Date: September 10, 2026.

---

## 1. Problem Statement & Positioning

Digital forensic triage tooling splits into paid enterprise suites (EnCase, FTK), priced out of reach of teaching labs and under-resourced investigators, and free mature tools (Autopsy, PhotoRec) that already serve the access-gap audience.

**SPECTER is an educational reference implementation of core forensic techniques** — structural signature carving, type-aware entropy triage, evidence-integrity verification, and tamper-evident audit logging — built to demonstrate mastery of the underlying computer science (file formats, I/O performance, applied cryptography, systems programming) through a codebase small and readable enough to be *read and modified by students*. As a secondary benefit it functions as a best-effort, lightweight triage utility. It is **explicitly not a production forensic suite and not suitable for court-admissible workflows** (§19).

## 2. Claims and Evidence

Every claim this project makes is mapped to the test that substantiates it. Claims without a test do not appear in the writeup.

| Claim | Test |
| --- | --- |
| Readable/modifiable by students (teaching value) | Student modification study, §16.5; module map & lab exercises, §11.4 |
| Carving correctness | Corpora C1–C3 with byte-exact scoring, §16.1 |
| Triage flags the right things | Labeled corpus with per-type ROC, §16.2 |
| Integrity layer detects tampering | Tamper suite incl. suffix deletion, §16.3 |
| Audit chain detects editing and (bounded) deletion | Tamper suite, §16.3 |
| Lightweight footprint | Resource comparison vs PhotoRec **and** Autopsy, §16.4 |
| Works fully offline | Network-disabled run, §16.6 |
| Deterministic, reproducible | Golden regression + pinned seeds, §16.7 |

## 3. Related Work

| Tool | Model | Honest relationship |
| --- | --- | --- |
| Autopsy / Sleuth Kit | Free, open-source | Mature, industry-standard; heavier JVM footprint; does far more per ingest run than SPECTER ever will |
| PhotoRec / TestDisk | Free, single C binary | The honest *lightweight* comparator — SPECTER loses to it on footprint and on format coverage; SPECTER's differentiators are case management, integrity layer, audit trail, readability |
| EnCase / FTK | Paid, enterprise | Priced out of the access-gap audience entirely |
| Bulk Extractor | Free | Bulk pattern/PII extraction at scale; SPECTER's keyword search is case-scoped, not a substitute |

Academic anchoring (full citations §21): DFRWS carving challenges, Pal & Memon's bifragment gap carving, Garfinkel's forensic corpora, and the **NIST CFTT tool-test methodology**, which the §16.1 carving benchmark deliberately follows rather than reinventing.

## 4. System Architecture

```text
+--------------------------------------------------------------+
|  UI: server-rendered Jinja2 + htmx                          |
|  (case dashboard, triage view, hex viewer, audit trail)     |
|  ~300 lines of JS total, only for hex-viewer navigation      |
+------------------------------+-------------------------------+
                               | HTTP
                               v
+--------------------------------------------------------------+
|  API: FastAPI                                                |
|  auth (JWT, argon2id), case CRUD, job submission/status,     |
|  artifact serving (IDs, not paths), chain verify, manifest   |
+------------------------------+-------------------------------+
                               |
              +----------------+-----------------+
              v                                  v
+---------------------------+   +----------------------------------+
| Worker pool               |   | SQLite (WAL mode, busy_timeout) |
| ProcessPoolExecutor       |-->| users, cases, images, chunks,    |
| carve / hash / triage     |   | artifacts, jobs, audit entries,  |
| jobs, state in job table  |   | manifests                        |
+-----+---------------------+   +----------------------------------+
      | mmap PROT_READ / ACCESS_READ (read-only, never writable)
      v
+---------------------------+        +---------------------------+
| Source image (.dd/.img)   |        | Case directory (FS)       |
| registered by path or     |        | carved artifact files,    |
| verified copy             |        | export bundles, manifests |
+---------------------------+        +---------------------------+
```

Decisions made (this fork is resolved, not deferred):

- **Single-analyst default:** SQLite (WAL), in-process `ProcessPoolExecutor`. No Redis, no Celery. PostgreSQL/Celery is a documented future deployment profile only.
- **React SPA is dropped.** Rationale: worst contribution-per-hour component for the stated claims; the teaching goal is forensics, not frontend. Server-rendered templates keep the codebase Python-readable end-to-end except the hex viewer's navigation script.
- **Carved artifacts live on the filesystem** under the case directory; the database stores metadata and hashes only. Storing artifact bytes in SQLite is an anti-pattern at GB scale.
- **Jobs are persisted in a job table**, not in-memory futures. A killed process leaves the job marked failed; carving is deterministic, so re-running a job is idempotent (artifacts overwrite, then dedupe).
- **Audit appends are serialized through one path** (§8), even across the API process and worker processes.
- Module map (a teaching deliverable): `specter.carve`, `specter.integrity`, `specter.triage`, `specter.audit`, `specter.jobs`, `specter.api`, `specter.ui`.

## 5. Language & Performance Envelope

Python is sufficient under one architectural invariant: **Python-level code executes per candidate match and per artifact — never per byte of the image.** All per-byte work stays in C: `bytes.find` for signature scanning, `hashlib` (OpenSSL) for SHA-256, `Counter` for byte histograms. Expected envelope on the reference laptop (§13): hashing ~0.3–1.5 GB/s per core depending on SHA-NI availability; scanning memory-bandwidth-bound once pages are resident; entropy ~tens of µs per 4 KB block, and it runs only on recovered artifacts (bounded), never over the whole image.

CPU-bound parallelism (chunk hashing, triage) uses `ProcessPoolExecutor`; read-only mmap pages are shared across workers. Non-Python surface: ~300 lines of JavaScript. Escape hatches, used **only if §9's acceptance targets fail**: a C/Rust extension for fused multi-pattern search (Aho-Corasick), and `libewf` bindings for E01 — both explicitly future work.

## 6. Evidence Lifecycle & Import Semantics

1. **Registration** — an image is added to a case either *by path* (default: no copy; anchored immediately by hashing — moving the file later is detected and reported, not silent) or as a *verified copy* (hash source → copy → re-hash → compare; doubles disk usage, documented).
2. **Acquisition hashing** — one sequential pass over the image computes the whole-image SHA-256 *and* all chunk hashes (§7) in a single read of the data.
3. **Carving** (§9), **triage** (§10), **review** — every action audited (§8).
4. **Anchoring** — case integrity manifest exported out-of-band (§7.3).

Precision on the read-only claim: `PROT_READ`/`ACCESS_READ` prevents **SPECTER itself** from writing to the image; it does not prevent *other processes* from modifying the file — detecting that is the hashes' job. 64-bit platforms only (§13); a read-only whole-file mmap is demand-paged, so mapping images larger than RAM is safe and no windowed-mapping workaround is needed.

## 7. Integrity Design

### 7.1 Components and their distinct roles

| Component | Role |
| --- | --- |
| Whole-image SHA-256 | **Detects** any change to the image (baseline, matches industry practice) |
| Chunk hash list (default 4 MB, stored per chunk) | **Localizes** a change to a chunk without re-hashing the image |
| Merkle root over the chunk hashes | **Compresses** the chunk set into one 32-byte value that can be anchored out-of-band and verified with O(log n) proofs |

Stated plainly: with a locally-stored root, a flat chunk-hash list gives identical tamper-evidence at lower complexity. The Merkle tree earns its complexity **only** because of the out-of-band manifest below. This is the difference between this spec and a decorative Merkle tree.

### 7.2 Proof-verification endpoint (in scope, semantics fixed)

For an artifact spanning `[offset, offset+length)`: re-read that range from the image, hash it, compare to the artifact's stored SHA-256; additionally verify Merkle proofs for every chunk the range intersects against the anchored root. Artifact ranges need not be chunk-aligned — the endpoint verifies whole covering chunks plus the byte-range hash.

### 7.3 Out-of-band anchor: the case integrity manifest

On case close and on demand, SPECTER exports a manifest containing: case ID, per-image whole-image SHA-256 and Merkle root, the audit chain head hash + sequence number, tool version, UTC timestamp. The examiner stores this **out of band** — printed into the physical case file, or on separate media. A verify command later re-derives all values and compares against the manifest.

**Honest limits, stated in the writeup:** interior edits to the image or audit chain are always detectable. *Suffix* deletion is detectable only back to the last exported manifest. An attacker with access to both the database and the image **before** any manifest export can rewrite everything undetectably. External key signing is future work; the manifest is tamper-evidence against corruption and casual tampering, not non-repudiation.

## 8. Hash-Chained Audit Log

- **Serialization:** entries are canonical JSON (sorted keys, UTF-8, no insignificant whitespace). `entry_hash = SHA256(b"specter-audit-v1:" + canonical_json)`, where the JSON contains `seq`, `case_id`, `prev_hash`, `actor`, `action`, target references, a config snapshot (signature-table version, job parameters), and a UTC ISO-8601 timestamp. Canonical serialization eliminates the field-boundary ambiguity of raw `||` concatenation; the version tag gives domain separation.
- **Chain:** per-case, genesis `= SHA256(b"specter-genesis:" + case_id)`. Chain order is authoritative; wall-clock timestamps are advisory.
- **Single writer:** appends execute inside a `BEGIN IMMEDIATE` SQLite transaction (read last hash → compute → insert → commit). This serializes the chain correctly across the API process and all workers.
- **Verification:** O(n) chain walk per case, exposed as an API endpoint and a UI "verify chain" button. Chain heads are checkpointed into every manifest export (§7.3), which is what bounds suffix deletion.
- Every lifecycle action is an entry: image registration, hash computed, job submitted/finished, artifact recovered/tagged/exported, manifest exported, chain verified.

## 9. Carving Engine

### 9.1 I/O and scan structure

- Read-only mmap via a platform accessor (Unix `PROT_READ`; Windows `ACCESS_READ`). 64-bit required.
- **Windowed single-pass scanning:** the image is processed in sequential windows (e.g., 128 MB) with a small boundary overlap; *all* signature searches run within each window before advancing. Running 9 whole-image `find()` passes instead would re-read an image larger than RAM from disk nine times.
- **Sector alignment filter (default on):** candidate headers must occur at 512-byte-aligned offsets (configurable to 4096 or off). This is the single cheapest false-positive reducer in carving.
- Wording honesty: mmap "avoids user-space buffering"; end-to-end zero-copy is not claimed.

### 9.2 Signature table — structural strategies, not naive footer scans

| Type | Header | Recovery strategy | Validation |
| --- | --- | --- | --- |
| JPG | `FF D8 FF` | Walk segment structure: markers are length-delimited; APPn segments (incl. EXIF thumbnails) are opaque — a thumbnail's internal EOI does **not** terminate the walk; entropy data ends at a real EOI | Segment lengths bounds-checked |
| PNG | full 8-byte signature | Chunk walk (length + type + data + CRC); end at `IEND` | **CRC-validated** — excellent false-positive rejection |
| GIF | `47 49 46 38` | Parse header + logical screen descriptor, then image descriptors and length-prefixed sub-blocks; trailer terminates | Structural, not first `00 3B` (which occurs inside LZW data) |
| PDF | `25 50 44 46` | Scan to **last** `%%EOF` within cap (incremental updates produce several); embedded PDFs handled by outermost-first policy | — |
| ZIP (incl. OOXML) | `50 4B 03 04` | Walk local file headers; if sizes are zero (streaming data descriptors), fall back to backward scan from EOCD `50 4B 05 06` | EOCD count cross-check when available |
| EXE | `4D 5A` | `MZ` alone is a 2-byte signature with mass false-positive potential — **accepted only if** `e_lfanew` is in bounds and `PE\0\0` validates; size = max(section `PointerToRawData + SizeOfRawData`) + headers | PE signature mandatory |
| SQLite | 16-byte `SQLite format 3\0` | Page size at offset 16 (value 1 ⇒ 65536), page count at 28; size = pages × page size | Both fields validated; stale counts flagged, cap fallback |
| BMP | `42 4D` | Size field at offset 2 — frequently wrong in the wild; validate, clamp, fall back to cap with a low-confidence flag | Bounds-clamped |
| MP4/MOV | `ftyp` at offset 4 | Box start = match − 4; box-size chaining with **size 0 = extends to EOF and size 1 = 64-bit largesize** handled; `ftyp`-first assumed | Box chain bounds-checked |

### 9.3 Defensive parsing (global rules)

1. Every length/offset read from the image is untrusted: clamp to image bounds before use; reject implausible values; a declared 4 GB size must neither crash nor hang the scanner.
2. Parsers are total: malformed structure degrades to footer-scan fallback plus a low-confidence flag — never an exception, never an unbounded loop.
3. All walking loops are bounded by the configurable safety cap.

### 9.4 Overlap policy, cursor advance, dedupe

Cursor advances past recovered regions (the performance argument from v2, retained — it avoids re-scanning proportional to recovered data). The v2 spec presented this as a pure win; the **correctness cost is now stated**: a false-positive header consumes its safety cap and masks anything inside that span. Mitigation: sector alignment + secondary validation (§9.2). Outermost-first carving suppresses inner duplicates; artifacts are deduplicated by SHA-256 (first occurrence kept, duplicate count recorded).

### 9.5 Acceptance criteria (make "lightweight" testable)

On the reference 8GB laptop (§13), cold cache: **signature scan ≥ 150 MB/s sustained; hashing pass ≥ 200 MB/s**; a 16 GB image fully processed (hash + carve + triage) in ≤ 30 minutes. Missing these targets triggers the optimization branch (§5) — before any C extension is written, the benchmark must have failed.

### 9.6 Known, documented limitation

Signature/structural carving cannot recover fragmented files; fragment-aware carving (Pal & Memon) is future work. No filesystem metadata is parsed — filenames/extensions are not recovered from the image (this is why the mismatch check moved, §10.2).

## 10. Triage Engine

### 10.1 Type-aware entropy analysis

Shannon entropy per 4 KB block — but **expected entropy is a property of the file type**. The v2 design flagged everything above 7.5, which flags essentially every carved JPEG. The checks are now directional:

| Type | Expected entropy | Anomaly flagged |
| --- | --- | --- |
| JPG, PNG, ZIP, MP4 | high (compressed) | **Low** entropy → truncated/corrupt carve |
| EXE | ~5–6.8 | High across large fraction → packed (e.g., UPX) |
| PDF, SQLite, BMP | mixed/low | High across majority → encrypted payload or misidentified type |

Thresholds are per-type and **derived from the labeled corpus** (§16.2); the evaluation reports per-type ROC/AUC rather than a single 7.5 operating point.

```python
def block_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())
```

### 10.2 Signature/extension mismatch — re-scoped to where it can actually fire

Carving recovers from raw images; there are no filenames in raw bytes, so mismatch against a carve-assigned label is vacuous. The check now applies to **loose files imported into a case** (a small, in-scope feature: analysts add files with real filenames, e.g., from a live triage collection), where signature-vs-extension disagreement is meaningful. OOXML containers recovered as ZIP are content-refined (via `[Content_Types].xml`) to `.docx/.xlsx/.pptx`.

### 10.3 Keyword search and known-file filtering (making "triage-first" real)

- **Keyword/regex search** over recovered artifacts (literal terms default; regex optional). Keyword search is the most-used triage function in practice; a triage tool without it is misnamed.
- **Known-hash filtering:** import a user-supplied hash list (NSRL-format CSV) and tag matching artifacts as known files — cheap, standard, and materially reduces analyst noise.
- **Deduplication** by SHA-256 across the case (§9.4).
- ONNX classifier: unchanged from v2 — included only if it beats this baseline on the labeled set. `triage.py` makes no outbound requests; any future AI summarization is on-device and visibly labeled "AI-generated, not verified."

## 11. Case Management & UI

- Case CRUD; roles: examiner (carve/tag/export), reviewer (view/comment), admin (users/cases); role check per endpoint.
- **Hex viewer (real):** server-rendered hex+ASCII pages (256 B/page) fetched by byte range; signature region, footer/boundary, and declared-size fields highlighted using carve metadata. Recovered files are **never rendered as their native type** (served `application/octet-stream`; hex/text views only) — recovered artifacts are attacker-controlled bytes, and browser parsers are a real attack surface. This is a deliberate, documented decision.
- Audit trail view with per-case "verify chain" button; manifest export from the UI.
- **Teaching deliverables (§2's primary claim made concrete):** `docs/TOUR.md` module map; four lab exercises with solutions on a separate branch ("add a RAR signature", "break a Merkle proof", "cause a chain break", "add an entropy profile").

## 12. Security Baseline

Table stakes, fixed first: secrets from environment with documented `.env.example` and fail-fast on placeholder values in production mode; randomly generated JWT secret; strict Pydantic schemas on every endpoint; rate limiting on auth; **argon2id password hashing**; artifact serving by ID with resolved paths required to remain under the case directory (path traversal); validated byte ranges on the hex-viewer endpoint; **export re-hashes the artifact and audits the result**.

## 13. Platform & Deployment

- **64-bit required** (demand-paged read-only mappings; no windowed-mapping workaround — that was a 32-bit concern).
- Linux is the primary development platform; Windows and macOS supported via the mmap accessor; CI runs a Linux + Windows matrix.
- Target hardware: 8 GB RAM laptop, no GPU, SQLite default profile — the machine §16.4 measures on.
- **Packaged install** (pip-installable package or PyInstaller single file), because the setup-friction comparison in §16.4 is only fair against a packaged product, not a dev environment.

## 14. Format Support

In scope: raw `.dd`/`.img`. Future work, stated plainly: E01/AFF via `libewf` bindings (real acquisitions are frequently E01); split images; live acquisition. No filesystem parsing (FAT/NTFS metadata) — documented, not discovered by omission.

## 15. Data Model

| Entity | Key fields |
| --- | --- |
| User | username, password_hash (argon2id), role |
| Case | name, status, created_by, timestamps |
| Image | case_id, path, size, whole_image_sha256, merkle_root, chunk_size, verified_copy_path? |
| Chunk | image_id, index, offset, sha256 |
| Artifact | image_id, type, offset, length, sha256, storage_path, confidence, entropy_profile, flags |
| LooseFile | case_id, filename, sha256, signature, mismatch_flag |
| Job | case_id, type, params, status, submitted_by, timestamps, error |
| AuditEntry | case_id, seq, prev_hash, payload (canonical JSON), entry_hash, actor, recorded_at (UTC) |
| Manifest | case_id, exported_at, image roots, audit_head, tool_version |

## 16. Evaluation Plan

### 16.1 Carving benchmark (CFTT-informed)

Three corpora, all generated by committed, seeded scripts:

- **C1 synthetic contiguous** (files of each type at known offsets — the easy case, reported as such).
- **C2 realistic:** a FAT32 volume (mtools) populated then files deleted — the classic carving scenario; also required for the Autopsy comparison to be valid (§16.4).
- **C3 adversarial:** truncated files (header, no footer); JPEG with EXIF thumbnail; nested ZIP; random data seeded with `MZ` and header strings; non-aligned headers; wrong BMP size fields; stale SQLite page counts.

**Scoring:** a true positive requires **byte-exact** recovery; partial carves are reported separately as completeness ratios (a GIF truncated at a random `00 3B` is not a recovery). False positives defined as carves with no ground-truth overlap. Metrics: recall, precision, completeness distribution, throughput. Cold-cache methodology stated (caches dropped between runs; both cold and warm reported).

### 16.2 Triage accuracy

Labeled set containing: encrypted (openssl/age), **compressed-but-not-encrypted** (gzip, ZIP, JPG, PNG — the classic false-positive class, absent from the v2 plan), plaintext, packed executables (UPX), and deliberately truncated carves. Per-type ROC/AUC over thresholds.

### 16.3 Tamper suite

Image byte flip → whole-image hash changes, owning chunk leaf changes, Merkle proof fails, manifest verify fails. Audit interior edit → chain breaks from that entry. **Audit suffix deletion** → detected only back to the last manifest (the documented boundary, tested as such, not overclaimed).

### 16.4 Resource comparison

Both **PhotoRec** and **Autopsy**, on the reference machine, same C2 image. Metrics: install-to-first-artifact time, peak RSS (same measurement methodology), disk overhead, and — critically — **a disclosure of what each tool actually completed**, because Autopsy's ingest does far more work than SPECTER's scan and a raw RAM number without workload disclosure is a rigged comparison. SPECTER is expected to *lose* to PhotoRec on footprint; the differentiators claimed are case management, integrity, audit, and readability (§16.5), and the writeup says so.

### 16.5 Teaching-value study

3–5 CS students not on the project: given `docs/TOUR.md` and the module map, complete a modification task ("add RAR signature `52 61 72 21 1A 07 00 00` and make its tests pass") — measure time-to-success and comprehension via a short code-tour quiz. This is the evidence for the project's primary claim.

### 16.6–16.7

Offline run (network disabled, full workflow). User study (3–5 participants, think-aloud on the triage workflow). Reproducibility: pinned dependencies, committed seeds and corpus scripts, results stored as JSON.

## 17. Testing Strategy

Unit tests with golden-offset fixtures per type, including every edge case in §9.2 (box size 0/1, out-of-bounds `e_lfanew`, wrong BMP size, premature `00 3B`, JPEG-with-thumbnail). Property-based tests (Hypothesis): Merkle proofs fail under any random chunk mutation; chain breaks under any interior entry mutation; suffix deletion behaves exactly as §16.3 documents. **Fuzzing:** random bytes after valid magics — parsers never raise and never hang. Determinism: same image twice → identical artifact list (golden regression). CI: Linux + Windows.

## 18. Project Plan

| Milestone | Weeks | Exit criteria |
| --- | --- | --- |
| M0 baseline + vertical slice | 1–3 | Repo, CI, security baseline; CLI: image → hash → carve → list |
| M1 carving engine | 4–8 | All 9 types structural, alignment, golden tests pass; **throughput targets met or optimization branch opened** |
| M2 integrity + audit | 9–12 | Chunks, tree, proofs, manifest export/verify, chain, property tests |
| M3 triage | 13–16 | Type-aware entropy, keyword, dedupe, loose-file import, hash sets |
| M4 UI | 17–20 | Server-rendered UI, hex viewer, roles, audit view |
| M5 evaluation | 21–24 | All §16 suites run, results committed |
| M6 writeup + packaging | 25–28 | Packaged install, thesis, buffer |

**Drop order (behind schedule, cut in this sequence):** ONNX (gated) → known-hash filtering → regex search (literal stays) → loose-file import (mismatch check with it) → MP4/GIF structural parsers (safety-cap fallbacks exist) → student study scale-down (never fully — it carries the primary claim).

**Risk register:** throughput miss (early acceptance test in M1; C-extension escape hatch); scope overrun (vertical slice first, drop order above); Autopsy comparison invalid (C2 corpus built in M1, not M5); audit concurrency bugs (single-writer + property tests); Windows mmap divergence (accessor abstraction + CI matrix); student recruitment (recruit at M2, peers as fallback).

## 19. Ethics, Safety, License

Synthetic and public corpora (e.g., Garfinkel's digital corpora) only — the tool is not to be run on real casework, and outputs are not evidence; stated in the README and thesis. No chain-of-custody claims (§1). The potential for forensic tooling to surface illicit content is acknowledged; the project's mitigation is its synthetic-data-only scope. License: MIT (a teaching tool students may modify needs one).

## 20. Out of Scope (documented, not discovered by omission)

E01/AFF; fragmented-file reassembly; externally *key-signed* anchoring (manifest anchoring is in scope; signing is future); PostgreSQL/Celery multi-analyst profile as primary; filesystem metadata parsing; live acquisition; ONNX unless time remains and it clears §16.2.

## 21. References

DFRWS 2006/2007 carving challenge reports · Pal & Memon, *Automated Reassembly of File Fragmented Images* (bifragment gap carving) · Garfinkel et al., digital forensics corpora · NIST CFTT, *Test Results for File Carving* · Merkle, *A Digital Signature Based on a Conventional Encryption Function* (1987) · Schneier & Kelsey, *Secure Audit Logs to Support Computer Forensics* (1999) · Shannon, *A Mathematical Theory of Communication* (1948) · Autopsy/Sleuth Kit documentation · PhotoRec documentation · ReFirm binwalk (entropy-heuristic precedent).

---

## Appendix A — Tech Stack

Python 3.11+ · FastAPI · Jinja2 + htmx (~300 lines JS) · SQLite (WAL) · `concurrent.futures` · `mmap` via platform accessor · `hashlib` SHA-256 · custom Merkle/chain · JWT + argon2id · Hypothesis (property tests) · optional: `onnxruntime` (gated).

## Appendix B — Traceability: v2 issues → v3 fixes

| v2 issue | Fixed in |
| --- | --- |
| Teaching claim unevaluated | §2 claims table, §11.4 labs, §16.5 study, §18 drop-order protects it |
| Merkle not earning its complexity | §7.1 role framing, §7.3 out-of-band manifest |
| Extension-mismatch check vacuous | §10.2 loose-file import re-scope |
| Entropy flags every JPEG | §10.1 type-aware directional checks, §16.2 corpus |
| Comparator flatters (no PhotoRec) | §3, §16.4 incl. workload disclosure + Autopsy-validity corpus |
| Scope/timeline risk, no plan | §18 milestones, drop order, risk register; React SPA cut (§4) |
| Naive footer strategies per format | §9.2 structural table |
| No sector alignment / defensive parsing / cursor-advance cost | §9.1, §9.3, §9.4 |
| No throughput criterion | §9.5 |
| Chain: concatenation ambiguity, no seq, tail truncation, multi-writer races | §8 |
| Windows mmap / address-space misconception | §6, §9.1, §13 (64-bit, accessor) |
| Artifacts-in-DB ambiguity; import copy-vs-reference | §4, §6 |
| Job persistence, WAL | §4 |
| Argon2id missing; artifact rendering risk | §12, §11 |
| Eval: easy-only corpus, scoring, cache methodology | §16.1 |
| No references/data model/testing/ethics/license/plan | §15, §17, §18, §19, §21 |
| GhostHunter undefined; diagram flow wrong | §4 (renamed to `specter.integrity`; flows corrected) |

---

**One caution to carry forward:** the strongest remaining risk in this plan is not any single technical item — it's M1's throughput gate. Run it early, on real spinning-disk-or-SSD hardware, before the architecture hardens around it. Everything else in this spec degrades gracefully via the drop order; performance doesn't.
