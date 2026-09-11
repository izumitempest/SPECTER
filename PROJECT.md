# SPECTER — Offline Forensic Triage Platform (Frozen Spec, v3.3)

**Final Year Project Documentation** — Godfrey Okoye University, Enugu, Department of Computer Science.

Author: Okwuchukwu Ekene Don Davies.

Date: September 10, 2026. Frozen at **v3.3** on September 11, 2026 (tag `spec-v3.3`).

**Status: FROZEN.** This document is the merged, canonical spec: base v3 + patches P-01…P-18 (levels v3.1–v3.3) + ERRATA-001, folded in. Patch provenance and intermediate versions live in `docs/spec/` (`PATCH-v3.1-v3.3.md`, `ERRATA-001.md`). This document supersedes all previously circulated intermediate versions.

---

## 0. Freeze Policy

1. **v3.3 is terminal.** Merged into this document and frozen at tag `spec-v3.3`.
2. New findings go to the **issue tracker** labeled `spec-errata` and must cite a patch ID. Only security-relevant or claim-invalidating findings reopen the document.
3. **Next external review: M1 code + benchmark output, week 8** — JPEG golden tests, the P-09 density gate, and the P-17 kill test.
4. Open empirical questions, not answerable by further prose review: JPEG state machine vs. real-camera files; scan throughput at 10⁴ candidates/GB; student-study signal; AUC stability at small n.

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
| ProcessPoolExecutor       |-->| users, cases, images, blobs,    |
| carve / hash / triage     |   | artifacts, jobs, audit entries,  |
| jobs, state in job table  |   | memberships, manifests           |
+-----+---------------------+   +----------------------------------+
      | mmap PROT_READ / ACCESS_READ (read-only, never writable)
      v
+---------------------------+        +---------------------------+
| Source image (.dd/.img)   |        | Case directory (FS)       |
| registered by path or     |        | carved blob store,        |
| verified copy             |        | export bundles, manifests |
+---------------------------+        +---------------------------+
```

Decisions made (each fork is resolved, not deferred):

- **Single-analyst default:** SQLite (WAL), in-process `ProcessPoolExecutor`. No Redis, no Celery. PostgreSQL/Celery is a documented future deployment profile only.
- **React SPA is dropped.** Rationale: worst contribution-per-hour component for the stated claims; the teaching goal is forensics, not frontend. Server-rendered templates keep the codebase Python-readable end-to-end except the hex viewer's navigation script.
- **Carved artifacts live on the filesystem** under the case directory (content-addressed blob store); the database stores metadata and hashes only. Storing artifact bytes in SQLite is an anti-pattern at GB scale.
- **Jobs are persisted in a job table**, not in-memory futures. A killed process leaves the job marked failed; carving is deterministic, so re-running a job is idempotent (artifacts overwrite, then dedupe).
- **Audit appends are serialized through one path** (§8), even across the API process and worker processes.
- Module map (a teaching deliverable): `specter.carve`, `specter.integrity`, `specter.triage`, `specter.audit`, `specter.jobs`, `specter.store`, `specter.api`, `specter.ui`.

### 4.1 Operations model [P-01, E-02, E-04, E-07]

1. **Per-image job lock:** at most one active carve/hash job per image; concurrent submissions queue (default) or reject with a clear, audited error.
2. **Blob write protocol:** content is written to a temp path in the case directory, then `os.replace`d to its content-addressed name. **Write order (pinned):** a worker's flush batch = artifact rows + blob row inserts/updates + audit entries in **one transaction**; renames execute **after** commit. Writer materialization check: existing row + existing file → skip write; existing row + missing file → re-materialize; new row → temp, commit, rename. Readers never see partial blobs; concurrent writers of identical content converge safely (WAL serializes). Reader-side ENOENT with row present and `status = active` → bounded retry (5 × 20 ms) to ride out the commit→rename window; only persistent ENOENT reports `lost` — surfaced to the caller, never an unhandled error. **Readers never repair:** re-carve decisions belong exclusively to reconciliation/GC. Only content-addressed names are ever GC-eligible — never temp-prefixed names.
3. **Disk management:** pre-job pre-flight (free space ≥ configurable multiple of image size, or per-case quota), re-checked every N artifacts; exhaustion stops the job cleanly, marks it `paused_disk`, and is audited. The verified-copy option requires 2× image size free before starting.
4. **Entropy profiles are stored aggregated** — head/tail/majority window statistics plus a histogram, never the full per-block series (~12.8K values per 50 MiB artifact; unaggregated across tens of thousands of artifacts is real DB bloat).
5. **Blob lifecycle — never delete inline.** Refcount decrements happen in transactions; physical deletion never occurs inside request/worker transactions. GC (periodic + on job completion) is **two-phase**:
   - *Phase 1:* `BEGIN IMMEDIATE`; delete rows with `refcount = 0`; `COMMIT`.
   - *Phase 2:* `BEGIN IMMEDIATE` (used purely as a cross-process mutex — no DB writes, rollback cost zero); re-verify each row is still absent (a recreated row means a concurrent writer won — skip); unlink; `COMMIT` empty. **≤ 256 unlinks per phase-2 pass**, remainder deferred — unbounded batches hold the writer mutex against concurrent flush batches, converting GC into a system-wide stall. Phase-2 unlink `ENOENT` is a benign skip, not a failure. Crash windows degrade only to orphan files (benign, collected by reconciliation).
   - **FS-mutation totality:** all unlink/replace sites catch-and-skip on Windows `PermissionError` (handle open elsewhere) and POSIX `ENOENT` (already gone); skipped paths defer to the next pass; no exception propagates past the job boundary. Writeup asymmetry stated: POSIX unlink-while-open succeeds (the reader keeps a valid fd to an unlinked inode); Windows refuses — the trigger is deletion-during-read.
   - **Reconciliation runs both directions:** files without rows are orphans from crashed writers (deleted); rows without files are flagged `lost`. **Temp-sweep rule:** temps carry the owning job ID (`<job_id>_<uuid>.tmp`); the sweep deletes temps of jobs **not in the active set**, with the age threshold (24 h default) as backstop only for job records that no longer exist — age alone would collect a long-running job's temps mid-write.
   - GC runs emit **one summary audit entry** (orphans removed, rows flagged lost) so the trail stays complete without per-blob noise.
   - **Backstop:** the blob store is a cache of the image's bytes; the image is the source of truth. Artifacts are deterministically re-derivable and verifiable against the chunk sidecar and manifest root — a lost blob costs a re-carve, never evidence.

## 5. Language & Performance Envelope

Python is sufficient under one architectural invariant: **Python-level code executes per candidate match and per artifact — never per byte of the image.** All per-byte work stays in C: `bytes.find` for signature scanning, `hashlib` (OpenSSL) for SHA-256, `Counter` for byte histograms. Expected envelope on the reference laptop (§13): hashing ~0.3–1.5 GB/s per core depending on SHA-NI availability; scanning memory-bandwidth-bound once pages are resident; entropy ~tens of µs per 4 KB block, and it runs only on recovered artifacts (bounded), never over the whole image.

CPU-bound parallelism (chunk hashing, triage) uses `ProcessPoolExecutor`; read-only mmap pages are shared across workers. Non-Python surface: ~300 lines of JavaScript. Escape hatches, used **only if §9's acceptance targets fail**: a C/Rust extension for fused multi-pattern search (Aho-Corasick), and `libewf` bindings for E01 — both explicitly future work.

## 6. Evidence Lifecycle & Import Semantics

1. **Registration** — an image is added to a case either *by path* (default: no copy; anchored immediately by hashing; a later move or replacement is **detected at the next access or verification action and reported then — no proactive filesystem monitoring**. Registration records stat metadata (size, mtime, inode), compared at every open, catching moves and replacements cheaply before any re-hashing.) or as a *verified copy* (hash source → copy → re-hash → compare; doubles disk usage, documented).
2. **Acquisition hashing** — one sequential pass over the image computes the whole-image SHA-256 *and* all chunk hashes (§7) in a single read of the data.
3. **Carving** (§9), **triage** (§10), **review** — every action audited (§8).
4. **Anchoring** — case integrity manifest exported out-of-band (§7.3).

Precision on the read-only claim: `PROT_READ`/`ACCESS_READ` prevents **SPECTER itself** from writing to the image; it does not prevent *other processes* from modifying the file — detecting that is the hashes' job. 64-bit platforms only (§13); a read-only whole-file mmap is demand-paged, so mapping images larger than RAM is safe and no windowed-mapping workaround is needed.

## 7. Integrity Design

### 7.1 Components and their distinct roles [P-03, E-03]

| Component | Role |
| --- | --- |
| Whole-image SHA-256 | **Detects** any change to the image (baseline, matches industry practice) |
| Chunk hash sidecar (`<image_id>.chunks`) | **Localizes** a change to a chunk without re-hashing the image; O(1) leaf lookup |
| Merkle root over the chunk hashes | **Compresses** the chunk set into one 32-byte value that can be anchored out-of-band and verified with O(log n) proofs |

Stated plainly: with a locally-stored root, the flat chunk-hash list gives identical tamper-evidence at lower complexity. The Merkle tree earns its complexity **only** because of the out-of-band manifest below. This is the difference between this spec and a decorative Merkle tree.

**Sidecar format (pinned):** `<image_id>.chunks` — a flat array of 32-byte SHA-256 values; `chunk_hash(i)` = bytes `[i·32, (i+1)·32)`. The DB stores the sidecar path, chunk size, and the Merkle root. Rationale: flat-array layout gives O(1) leaf lookup, sequential write during the single acquisition pass, zero index machinery, and a trivially auditable format. (Row-per-chunk was workable — 262,144 rows ≈ 13–15 MB per TB imaged — the sidecar is simply simpler.) Sidecar integrity is committed by the root: tampered leaves produce proofs that fail against the anchored root. Optional `chunks_file_sha256` enables image-free sidecar self-checks.

**Partial trailing chunk (pinned):** the final chunk is hashed at its **exact remaining byte length, unpadded**; chunk count = `ceil(size / chunk_size)`; acquisition and verification use the identical rule, so artifacts in the final chunk verify like any other. Golden fixture: an image size deliberately not divisible by 4 MB.

**Merkle construction (pinned):** levels with an odd node count > 1 duplicate the final node (parent = `SHA256(n‖n)`); pairwise parents are `SHA256(left‖right)` over fixed-width 32-byte concatenations; a single leaf's root is the leaf hash itself. Pinning matters because the root is exported out-of-band — independent re-derivation (third parties, re-implementations, future versions) must compute identically. Fixtures: an image sized for an odd chunk count and a partial trailing chunk (one fixture exercises both), plus a sub-chunk-size image (n = 1).

### 7.2 Proof-verification endpoint (in scope, semantics fixed)

For an artifact spanning `[offset, offset+length)`: re-read that range from the image, hash it, compare to the artifact's stored SHA-256; additionally verify Merkle proofs for every chunk the range intersects against the anchored root. Artifact ranges need not be chunk-aligned — the endpoint verifies whole covering chunks plus the byte-range hash.

### 7.3 Out-of-band anchor: the case integrity manifest

On case close and on demand, SPECTER exports a manifest containing: case ID, per-image whole-image SHA-256 and Merkle root, the audit chain head hash + sequence number, tool version, UTC timestamp. The examiner stores this **out of band** — printed into the physical case file, or on separate media. A verify command later re-derives all values and compares against the manifest.

**Honest limits, stated in the writeup:** interior edits to the image or audit chain are always detectable. *Suffix* deletion is detectable only back to the last exported manifest. An attacker with access to both the database and the image **before** any manifest export can rewrite everything undetectably. External key signing is future work; the manifest is tamper-evidence against corruption and casual tampering, not non-repudiation.

## 8. Hash-Chained Audit Log [P-04, E-09]

**(a) Canonical serialization (pinned):**

```python
entry_hash = SHA256(b"specter-audit-v1:" + json.dumps(
    payload, sort_keys=True, separators=(",", ":"),
    ensure_ascii=True, allow_nan=False).encode("utf-8"))
```

Payloads permit integers, strings, booleans, and null only — **no floats**. Timestamps are ISO-8601 strings; sizes are integers. The verification path calls exactly this function; CI round-trips serialize → hash → verify on Linux and Windows.

- An entry's payload contains `seq`, `case_id`, `prev_hash`, `actor`, `actor_role`, `action`, target references, a config snapshot (signature-table version, job parameters), and a UTC ISO-8601 timestamp. The version tag in the hash input gives domain separation; canonical serialization eliminates the field-boundary ambiguity of raw `||` concatenation.
- **Chain:** per-case, genesis `= SHA256(b"specter-genesis:" + case_id)`. Chain order is authoritative; wall-clock timestamps are advisory. **`seq` is commit order by design** — the chain is a chronological log of committed transitions; evidence spatial order lives in artifact offsets; concurrent jobs on different images interleave in commit order by design, not defect.

**(b) Metrics and the chain:** analytical measurements (entropy, confidence) live in the artifact and triage tables, referenced by ID — they do not enter the chain. Where a metric must appear in a payload: pinned-precision decimal string (`"7.4200"`, 4 dp) or a scaled integer with the scale in the field name (`confidence_bp: 85`).

**(c) Write model — transactional audit co-commitment (pinned):** every entry describing a database state transition is inserted **in the same transaction as the transition it describes**. Workers buffer *payloads only* (unhashed, unsequenced); `seq`, `prev_hash`, and `entry_hash` are computed exclusively inside the `BEGIN IMMEDIATE` flush transaction, against the live tail. Case DB: WAL + `PRAGMA synchronous=FULL` (one fsync per ≤500-entry batch, amortized).

Consequences, stated in the writeup: (1) the chain's crash-consistency equals SQLite's — no committed transition lacks its entry, and no entry describes a transition that never committed; (2) a worker crash loses nothing that existed — the un-flushed batch's rows and entries vanish together, the supervisor audits the job failure, and deterministic re-running recovers the work; (3) export side-effects carry a milliseconds-scale crash window, documented, with manifest verification as reconciliation; (4) metrics stay out of the chain per (b).

Rejected alternatives (recorded): in-memory `multiprocessing.Queue` to a single writer (converts bounded contention into silent event loss; the writer dies with its queue); per-worker staging-file WAL (buys durability for events whose transitions would still be lost — co-commitment makes event durability identical to transition durability).

- **Verification:** O(n) chain walk per case, exposed as an API endpoint and a UI "verify chain" button. Chain heads are checkpointed into every manifest export (§7.3), which is what bounds suffix deletion.
- Every lifecycle action is an entry: image registration, hash computed, job submitted/finished, artifact recovered/tagged/exported, manifest exported, chain verified.

## 9. Carving Engine

### 9.1 I/O and scan structure [P-05]

- Read-only mmap via a platform accessor (Unix `PROT_READ`; Windows `ACCESS_READ`). 64-bit required.
- **Windowed single-pass scanning:** the image is processed in sequential windows (e.g., 128 MB) with a **fixed 64-byte boundary overlap** (≥ longest signature, 16 B); *all* signature searches run within each window before advancing. Running 9 whole-image `find()` passes instead would re-read an image larger than RAM from disk nine times.
- **Sector alignment filter (default on):** candidate headers must occur at 512-byte-aligned offsets (configurable to 4096 or off). This is the single cheapest false-positive reducer in carving.
- **Window invariant (pinned):** windows bound the scan pass, never the parsers. Structural parsers read directly from the full read-only mapping and are bounded only by the safety cap and image length. A parser that consults window boundaries is a bug. The overlap must **not** be set to the safety cap: that re-scans ~40% of the image to solve a problem that cannot occur.
- Wording honesty: mmap "avoids user-space buffering"; end-to-end zero-copy is not claimed.

### 9.2 Signature table — structural strategies, not naive footer scans

| Type | Header | Recovery strategy | Validation |
| --- | --- | --- | --- |
| JPG | `FF D8 FF` | Two-mode state machine (marker ↔ entropy); pinned below | Segment lengths bounds-checked; E-01 rules |
| PNG | full 8-byte signature | Chunk walk (length + type + data + CRC); end at `IEND` | **CRC-validated** — excellent false-positive rejection |
| GIF | `47 49 46 38` | Parse header + logical screen descriptor, then image descriptors and length-prefixed sub-blocks; trailer terminates. Per sub-block, bounds-check `offset + size` against both the safety cap and the image length **before** advancing; overrun terminates with a low-confidence flag | Structural, not first `00 3B`; overrun → low-confidence flag |
| PDF | `25 50 44 46` | Scan to **last** `%%EOF` within cap (incremental updates produce several); embedded PDFs handled by outermost-first policy | — |
| ZIP (incl. OOXML) | `50 4B 03 04` | Walk local file headers; if sizes are zero (streaming data descriptors), fall back to backward scan from EOCD `50 4B 05 06` | EOCD count cross-check when available |
| EXE | `4D 5A` | `MZ` alone is a 2-byte signature with mass false-positive potential — **accepted only if** `e_lfanew` is in bounds and `PE\0\0` validates; size = max(section `PointerToRawData + SizeOfRawData`) + headers | PE signature mandatory |
| SQLite | 16-byte `SQLite format 3\0` | Page size at offset 16 (value 1 ⇒ 65536), page count at 28; size = pages × page size | Both fields validated; stale counts flagged, cap fallback |
| BMP | `42 4D` | Size field at offset 2 — frequently wrong in the wild; validate, clamp, fall back to cap with a low-confidence flag | Bounds-clamped |
| MP4/MOV | `ftyp` at offset 4 | Box start = match − 4; box-size chaining with **size 0 = extends to EOF and size 1 = 64-bit largesize** handled; `ftyp`-first assumed | Box chain bounds-checked |

**JPEG — two-mode state machine (pinned, P-06 + E-01):** *Marker mode:* markers are length-delimited; APPn/DQT/SOF/DHT consumed opaquely via length (an EXIF thumbnail's internal EOI cannot terminate the walk); leading `FF` fill bytes are skipped before every marker code (`FF FF FF D9` = EOI with two fills). SOS switches to *entropy mode*: `FF 00` = stuffed literal (consume both); `FF D0–D7` = restart marker (consume both); `FF FF` = fill (consume one, re-peek); any other `FF xx` = real marker → return to marker mode; progressive JPEGs re-enter entropy mode at each subsequent SOS; `FF D9` in marker mode = EOI. A dangling `FF` at cap or image end with no byte to peek terminates via the fallback path — treated as no-EOI-found, low-confidence; **never** a marker parse. No EOI within cap → fallback: last `FF D9` within cap, low-confidence; else cap-bounded. Fixtures (regression tests required): `cjpeg` output (baseline, `-restart`, `-progressive`), a hex-edited fill-byte variant, and a truncated JPEG whose final byte is a literal `FF`. Implementation note: entropy-mode scanning costs ~4K Python iterations per MB (FF density ≈ 1/256), ~1–2 s/GB on JPEG-heavy images — profiled in **M1's clean-image throughput measurement**; a compiled regex matcher is the named optimization.

### 9.3 Defensive parsing (global rules) [P-07]

1. Every length/offset read from the image is untrusted: clamp to image bounds before use; reject implausible values; a declared 4 GB size must neither crash nor hang the scanner.
2. Parsers are total: malformed structure degrades to footer-scan fallback plus a low-confidence flag — never an exception, never an unbounded loop.
3. All walking loops are bounded by the configurable safety cap.
4. **O(1) rejection rule:** every candidate must be rejected in O(1) — alignment check, secondary signature (`PE\0\0`), first-chunk CRC (PNG), or a single bounds check — *before* any O(cap) structure or footer scan. A false positive that reaches a cap-sized scan is a performance bug, not load. Property tests enforce that no rejection path exceeds O(1) work.

### 9.4 Overlap policy, cursor advance, dedupe [P-08, E-06]

- **Deduplicate bytes, never records.** Every carved instance is its own `Artifact` row with its own offset, length, and confidence — each instance's location is evidence. Identical content is stored once via `content_sha256` → `Blob`.
- **Cursor semantics (pinned):** one cursor shared by all signature searches; recovered *and attempted* regions — including cap-bounded low-confidence fallbacks — are skipped by all signature types; cross-type nesting is suppressed by policy (C3 ground truth marks nested instances expected-suppressed). "Global" means global across signature searches **within one carve job**, which executes as a single sequential scan (P-05's sequential windows) in one worker process; the cursor is that job's process-local state. Pool parallelism applies across jobs (different images, per the per-image lock) and within a job to chunk hashing and artifact triage — **not** to the scan loop, whose state is inherently sequential. If the P-09 gate ever demands parallel candidate validation, the escape hatch is dispatching candidates to the pool with the cursor advancing only past the header, and suppressing masked regions post-hoc — a design fork, not specced until the gate fails.
- **Masking is measured, not assumed:** the v2 framing (cursor advance as pure win) is corrected by reporting the masking cost — the evaluation measures the masking rate, i.e. known files lost inside fallback spans, alongside recall.
- Outermost-first carving suppresses inner duplicates (C3 marks nested instances expected-suppressed).

### 9.5 Acceptance criteria (make "lightweight" testable) [P-09]

On the reference 8GB laptop (§13), cold cache: **signature scan ≥ 150 MB/s sustained; hashing pass ≥ 200 MB/s**; a 16 GB image fully processed (hash + carve + triage) in ≤ 30 minutes. Missing these targets triggers the optimization branch (§5) — before any C extension is written, the benchmark must have failed.

**Density gate (pinned):** clean-image throughput does not predict adversarial behavior; failures come from candidate density, and random bytes rarely produce aligned, structure-plausible candidates (~32 aligned `MZ` per GB of random data). The density corpus is the P-17 mutation fuzzer's output — valid fixtures with corrupted length/CRC/size fields — planted at aligned offsets at controlled densities (sweep 10³–10⁵ candidates/GB). Gate: **effective throughput at 10⁴/GB must not fall below 50% of clean-image throughput.** Run at week 4–5, not week 8 — the one gate whose failure forces architectural change.

### 9.6 Known, documented limitation

Signature/structural carving cannot recover fragmented files; fragment-aware carving (Pal & Memon) is future work. No filesystem metadata is parsed — filenames/extensions are not recovered from the image (this is why the mismatch check moved, §10.2).

## 10. Triage Engine

### 10.1 Type-aware entropy analysis [P-10]

Shannon entropy per 4 KB block — but **expected entropy is a property of the file type**. The v2 design flagged everything above 7.5, which flags essentially every carved JPEG. The checks are now directional:

| Type | Expected entropy | Anomaly flagged |
| --- | --- | --- |
| JPG, PNG, ZIP, MP4 | high (compressed) | **Low** entropy → truncated/corrupt carve |
| EXE | ~5–6.8 | High across large fraction → packed (e.g., UPX) |
| PDF, SQLite, BMP | mixed/low | High across majority → encrypted payload or misidentified type |

**Position windows (pinned):** directional checks are defined over block-position windows, not whole-artifact averages: the truncated/corrupt flag = tail-window entropy below the type's compressed-floor with a normal head. The signal depends on trailing foreign bytes — precision/recall is measured against §16.2's truncated-carve class, not assumed. Entropy profiles are stored aggregated (§4.1).

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

### 10.3 Keyword search and known-file filtering (making "triage-first" real) [P-11, E-05]

- **Streaming search:** per-artifact mmap scanned in 1 MiB slices; literals via `bytes.find` (C-speed); regex via windowed `re.finditer`; memory O(window); findings are `TriageFinding` rows with byte offsets. FTS5 rejected: tokenization is wrong for binary artifacts and arbitrary regex.
- **Regex — computed-overlap and clamp paths:** at query parse time, compute the pattern's maximum match length from the AST where available; bounded patterns scan with overlap = computed maximum. **Unbounded patterns (`*`, `+`, `{n,}`) are accepted, not rejected**, and routed to the clamp path: evaluated with truncation-detection (a match ending exactly at the window boundary is re-evaluated against an extension buffer), hard-capped at 64 KiB default, with matches hitting the cap **flagged truncated** and surfaced to the analyst — unbounded quantifiers over binary data yield pathological matches, and the forensic idiom is bounded context windows (e.g. `keyword.{0,200}`). Patterns whose computed maximum exceeds the cap, or whose AST cannot be analyzed (`re._parser` is semi-internal), also take the clamp path. Property tests: unbounded patterns yield flagged results; boundary-spanning matches are found for every accepted pattern.
- **Known-file hash sets, disk-backed:** NSRL-class lists are never loaded into RAM. An import command compiles a CSV once into a sorted binary array of 32-byte hashes (binary-search lookup, zero resident memory) plus an optional Bloom prefilter (~180 MB at 1% FP for 150M entries). A false "known" verdict suppresses an artifact from review — the asymmetric, harmful error — so Bloom hits are always confirmed by exact binary search before tagging.
- **Deduplication** by content across the case (§9.4).
- ONNX classifier: unchanged from v2 — included only if it beats this baseline on the labeled set. `triage.py` makes no outbound requests; any future AI summarization is on-device and visibly labeled "AI-generated, not verified."

## 11. Case Management & UI

- Case CRUD; roles: examiner (carve/tag/export), reviewer (view/comment), admin (users/cases); role check per endpoint.
- **Case-scoped membership [P-12]:** `CaseMember(user_id, case_id, role_in_case)`; every case-scoped endpoint resolves the resource's case and requires membership or admin before opening any file handle (§12). Cross-case access returns 404.
- **Hex viewer (real):** server-rendered hex+ASCII pages (256 B/page) fetched by byte range; signature region, footer/boundary, and declared-size fields highlighted using carve metadata. Recovered files are **never rendered as their native type** (served `application/octet-stream`; hex/text views only) — recovered artifacts are attacker-controlled bytes, and browser parsers are a real attack surface. This is a deliberate, documented decision.
- Audit trail view with per-case "verify chain" button; manifest export from the UI.
- **Teaching deliverables (§2's primary claim made concrete):** `docs/TOUR.md` module map; four lab exercises with solutions on a separate branch ("add a RAR signature", "break a Merkle proof", "cause a chain break", "add an entropy profile").

## 12. Security Baseline [P-12]

**Case-scoped authorization (normative):** every case-scoped endpoint resolves the resource's case and requires `CaseMember` membership **or admin** before opening any file handle, via a FastAPI dependency (`require_case_access`) so the check is structurally impossible to omit from a new route. Cross-case access returns **404, not 403** (no existence oracle). **Admin semantics (normative):** admins bypass `CaseMember`; every audit entry records the actor's role, so admin cross-case access is visible in the trail, never silent.

**Auth lifecycle:** JWT secret generated once at deployment bootstrap (`specter init`, 256-bit, 0600 keyfile or env), persists across restarts; production fails fast if absent; access tokens expire (8 h default); argon2id pinned (`memory_cost=65536 KiB, time_cost=3, parallelism=1`).

**Transport and containment:** JWT in an httponly cookie + `SameSite=Lax` + double-submit CSRF token on every form (bearer/localStorage rejected — trades CSRF for XSS token theft); CSP headers set. Rate limiting: in-process token-bucket dependency on auth routes, named. Path containment: `os.path.realpath` + commonpath comparison at serve time (sibling-prefix and symlink escapes defeat naive prefix checks).

Table stakes, fixed first: secrets from environment with documented `.env.example` and fail-fast on placeholder values in production mode; strict Pydantic schemas on every endpoint; validated byte ranges on the hex-viewer endpoint; **export re-hashes the artifact and audits the result**.

## 13. Platform & Deployment [E-07]

- **64-bit required** (demand-paged read-only mappings; no windowed-mapping workaround — that was a 32-bit concern).
- Linux is the primary development platform; Windows and macOS supported via the mmap accessor; CI runs a Linux + Windows matrix.
- Target hardware: 8 GB RAM laptop, no GPU, SQLite default profile — the machine §16.4 measures on.
- **Packaged install** (pip-installable package or PyInstaller single file), because the setup-friction comparison in §16.4 is only fair against a packaged product, not a dev environment.
- **Deployment constraint (normative):** the reference deployment runs a **single API process**. Multi-worker Uvicorn/Gunicorn is out of scope for v1: it forks the in-process job pool, multiplies audit writers, and silently partitions the in-process rate limiter. If that topology is ever introduced, rate-limit counters move to SQLite and job orchestration is reworked — documented, not implemented.

## 14. Format Support

In scope: raw `.dd`/`.img`. Future work, stated plainly: E01/AFF via `libewf` bindings (real acquisitions are frequently E01); split images; live acquisition. No filesystem parsing (FAT/NTFS metadata) — documented, not discovered by omission.

## 15. Data Model [P-13]

| Entity | Key fields |
| --- | --- |
| User | username, password_hash (argon2id), role (examiner/reviewer/admin) |
| Case | name, status, created_by, timestamps |
| Image | case_id, path, size, whole_image_sha256, merkle_root, chunk_size, chunks_path, chunks_file_sha256?, verified_copy_path? |
| Blob | sha256 (PK), storage_path, size, refcount, status (`active`/`lost`) |
| Artifact | image_id, type, offset, length, confidence, content_sha256 (FK → Blob), entropy_profile (aggregated), flags |
| LooseFile | case_id, filename, sha256, signature, mismatch_flag |
| Job | case_id, type, params, status, submitted_by, timestamps, error |
| CaseMember | user_id, case_id, role_in_case |
| AuditEntry | case_id, seq, prev_hash, payload (canonical JSON), entry_hash, actor, actor_role, recorded_at (UTC) |
| Manifest | case_id, exported_at, image roots, audit_head, tool_version |
| TriageFinding | artifact_id, kind, offset, length, detail |

Notes: `Chunk` was removed — per-chunk hashes live in the sidecar file (P-03). Per-instance artifact `offset`/`length`/`confidence` retained; identical content stored once via `Blob` (P-08). Backfill-audit: tables touching audit co-commitment are `Artifact`, `Job` (P-04c/E-08); `Blob` rows are cache state and carry no audit entries.

## 16. Evaluation Plan

### 16.1 Carving benchmark (CFTT-informed)

Three corpora, all generated by committed, seeded scripts:

- **C1 synthetic contiguous** (files of each type at known offsets — the easy case, reported as such).
- **C2 realistic:** a FAT32 volume (mtools) populated then files deleted — the classic carving scenario; also required for the Autopsy comparison to be valid (§16.4).
- **C3 adversarial:** truncated files (header, no footer); JPEG with EXIF thumbnail; nested ZIP; random data seeded with `MZ` and header strings; non-aligned headers; wrong BMP size fields; stale SQLite page counts.

**Scoring:** a true positive requires **byte-exact** recovery; partial carves are reported separately as completeness ratios (a GIF truncated at a random `00 3B` is not a recovery). False positives defined as carves with no ground-truth overlap. Metrics: recall, precision, completeness distribution, throughput, and the **masking rate** (§9.4). Cold-cache methodology stated (caches dropped between runs; both cold and warm reported).

### 16.2 Triage accuracy [P-14]

Labeled set containing: encrypted (openssl/age), **compressed-but-not-encrypted** (gzip, ZIP, JPG, PNG — the classic false-positive class, absent from the v2 plan), plaintext, packed executables (UPX), and deliberately truncated carves. Per-type ROC/AUC over thresholds, with **bootstrap confidence intervals and exact per-class counts** — point estimates alone are noise at this set size.

### 16.3 Tamper suite

Image byte flip → whole-image hash changes, owning chunk leaf changes, Merkle proof fails, manifest verify fails. Audit interior edit → chain breaks from that entry. **Audit suffix deletion** → detected only back to the last manifest (the documented boundary, tested as such, not overclaimed).

### 16.4 Resource comparison [P-15]

Both **PhotoRec** and **Autopsy**, on the reference machine, same C2 image. Metrics: install-to-first-artifact time, peak RSS (same measurement methodology), disk overhead, and — critically — **a disclosure of what each tool actually completed**, because Autopsy's ingest does far more work than SPECTER's scan and a raw RAM number without workload disclosure is a rigged comparison. SPECTER is expected to *lose* to PhotoRec on footprint; the differentiators claimed are case management, integrity, audit, and readability (§16.5), and the writeup says so. **Packaging:** pip-install is primary; if PyInstaller is used for parity, **onedir mode** — onefile self-extracts to a temp directory on *every* launch, silently skewing time-to-first-artifact on every run. Disclosed either way.

### 16.5 Teaching-value study [P-16]

3–5 CS students not on the project: given `docs/TOUR.md` and the module map, complete a modification task ("add RAR signature `52 61 72 21 1A 07 00 00` and make its tests pass") — measure time-to-success and comprehension via a short code-tour quiz. After the SPECTER task, each participant attempts a **timeboxed (30–45 min) comparable signature addition in PhotoRec's C source**; record success, time, a perceived-modifiability Likert, and prior Python/C experience as covariates. Fixed order (SPECTER first), order effects acknowledged; per-participant reporting; framed as indicative — no inferential statistics claimed at n=3–5. This is the evidence for the project's primary claim.

### 16.6–16.7

Offline run (network disabled, full workflow). User study (3–5 participants, think-aloud on the triage workflow). Reproducibility: pinned dependencies, committed seeds and corpus scripts, results stored as JSON.

## 17. Testing Strategy [P-17, E-08]

Unit tests with golden-offset fixtures per type, including every edge case in §9.2 (box size 0/1, out-of-bounds `e_lfanew`, wrong BMP size, premature `00 3B`, JPEG-with-thumbnail). Property-based tests (Hypothesis): Merkle proofs fail under any random chunk mutation; chain breaks under any interior entry mutation; suffix deletion behaves exactly as §16.3 documents. **Fuzzing:** random bytes after valid magics — parsers never raise and never hang. Determinism: same image twice → identical artifact list (golden regression). CI: Linux + Windows.

- **Mutation-based fuzzing** alongside random-bytes: valid fixtures mutated in length, CRC, size, box-size, `e_lfanew`, and page-count fields, plus random bit flips. Invariants: never raise, never hang, every input terminates as recovery-or-rejection with a confidence flag. The mutated corpus **doubles as the P-09 density corpus**.
- **Golden fixtures:** image size not divisible by the chunk size (P-03); JPEG recipe via committed script — `cjpeg -restart` and `cjpeg -progressive` over public-domain images — deterministic, license-clean, covering the entropy-mode traps.
- **Zero-length images** are rejected at registration with an audit entry.
- **Crash-consistency test (pinned wording):** `SIGKILL` a worker mid-carve on a deterministic corpus at a fixed schedule, then assert, **considering only committed rows**: (1) every Artifact/Job row present post-crash has its chain entry, and every entry's referenced row exists; (2) the job is marked failed with a failure entry; (3) the blob directory reconciles with rows after GC; (4) re-running the job reproduces identical artifacts. Un-flushed batches vanish coherently per co-commitment — the test must not treat their absence as failure.

## 18. Project Plan

| Milestone | Weeks | Exit criteria |
| --- | --- | --- |
| M0 baseline + vertical slice | 1–3 | Repo, CI, security baseline; CLI: image → hash → carve → list |
| M1 carving engine | 4–8 | All nine types structural **or demoted per drop order**, with demoted fallbacks passing the same golden tests; alignment, golden tests pass; **throughput targets met or optimization branch opened**; density gate run at week 4–5 (P-09), not week 8 |
| M2 integrity + audit | 9–12 | Sidecar, tree, proofs, manifest export/verify, chain, property tests, kill test |
| M3 triage | 13–16 | Type-aware entropy, keyword, dedupe, loose-file import, hash sets |
| M4 UI | 17–20 | Server-rendered UI, hex viewer, roles, audit view |
| M5 evaluation | 21–24 | All §16 suites run, results committed |
| M6 writeup + packaging | 25–28 | Packaged install, thesis, buffer |

**Drop order (behind schedule, cut in this sequence):** ONNX (gated) → known-hash filtering → regex search (literal stays) → loose-file import (mismatch check with it) → **JPEG structural walk → last-EOI-within-cap fallback** (APPn-opacity and alignment retained; recovers most real files; byte-exactness will differ — measured by the same fixtures) → MP4/GIF structural parsers (safety-cap fallbacks exist) → student study scale-down (never fully — it carries the primary claim).

**Risk register:** throughput miss (early acceptance test in M1; C-extension escape hatch); scope overrun (vertical slice first, drop order above); Autopsy comparison invalid (C2 corpus built in M1, not M5); audit concurrency bugs (single-writer + property tests); Windows mmap divergence (accessor abstraction + CI matrix); student recruitment (recruit at M2, peers as fallback); GC/writer races (two-phase GC + property tests, E-02).

## 19. Ethics, Safety, License

Synthetic and public corpora (e.g., Garfinkel's digital corpora) only — the tool is not to be run on real casework, and outputs are not evidence; stated in the README and thesis. No chain-of-custody claims (§1). The potential for forensic tooling to surface illicit content is acknowledged; the project's mitigation is its synthetic-data-only scope. License: MIT (a teaching tool students may modify needs one).

## 20. Out of Scope (documented, not discovered by omission)

E01/AFF; fragmented-file reassembly; externally *key-signed* anchoring (manifest anchoring is in scope; signing is future); PostgreSQL/Celery multi-analyst profile as primary; multi-worker API topology (E-07); filesystem metadata parsing; live acquisition; ONNX unless time remains and it clears §16.2.

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

## Appendix C — Rejected Prescriptions Register

Proposals rejected with grounds. Cite this register before re-proposing.

| Proposal | Source | Grounds |
| --- | --- | --- |
| Window overlap = safety cap (e.g. 50 MB) | Round 3 | Re-scans ~40% of the image; parsers are never window-bounded (P-05) |
| Remove DB handles from worker processes | Round 2 | Incoherent — workers persist artifact rows regardless |
| Audit via in-memory queue / synchronous IPC writer | Rounds 2, 4 | Converts bounded contention into event loss; superseded by co-commitment (P-04c) |
| Per-worker staging-file WAL | Round 4 | Durability for events whose transitions are lost anyway; co-commitment makes it moot |
| FTS5 for keyword search | Round 2 | Tokenizes text — wrong for binary artifacts and arbitrary regex |
| NSRL loaded into memory | Round 2 | 6 GB CSV → >10 GB RAM on an 8 GB target |
| Floats in chain payloads | Rounds 2, 4 | Canonical-form portability; excluded by rule (P-04b) |
| PyInstaller onefile | Round 3 | Self-extracts on every launch; skews all timing (P-15) |
| React SPA | Base v3 | Worst contribution-per-hour for the stated claims |
| First-footer scan strategies | Round 1 | Structural parsers specified instead (P-06) |
| Naive commit-then-unlink (GC) | Round 4 | Reintroduces the round-4 GC-vs-writer race; two-phase GC required (E-02) |
| Parallel scan-loop dispatch | Round 4 | "Architecturally invalid" — P-05 specifies sequential scan; parallel candidate validation is an unspecced fork until the P-09 gate fails (E-06) |
| Multi-worker API deployment | Round 4 | Forks the in-process job pool, multiplies audit writers, partitions the rate limiter; single-API-process is normative (E-07) |

## Appendix D — Corrected-Claims Register

External claims refuted with arithmetic. Retain for defense.

| Claim | Correction |
| --- | --- |
| "Gigabytes of B-tree overhead" (1 TB @ 4 MB chunks) | 262,144 rows ≈ 13–15 MB with `WITHOUT ROWID` |
| "SQLite deadlocks under worker load" | Single writer lock, no ordering cycle → contention resolved by `busy_timeout` |
| "Structural validation fails at window seams" | Parsers read the full mapping; windows order the scan only |
| "Non-aligned adversarial headers stress validation" | Non-aligned = cheap O(1) rejection; the stress case is aligned, structure-plausible candidates (~32 aligned `MZ`/GB in random data) |
| "onefile skews first run only" | Extracts on every launch |
| "Parallel blob upserts race" | WAL serializes all writers |
| v3.1's own Bloom size "~125 MB" | Correct value at 1% FP, 150M entries is ~180 MB (P-11, self-corrected) |
| "Irrecoverable loss" from blob deletion | Refuted: re-carve backstop + `lost` flagging; a lost blob costs a re-carve, never evidence |
| Regex rejection "unusable" for unbounded patterns | Overstated; clamp path adopted — unbounded patterns accepted and flagged truncated (E-05) |

---

**Two usage notes for this document:** the two registers (Appendices C/D) are its real long-term value — the immune system against re-litigating settled decisions under deadline pressure, yours or a reviewer's. New findings go to the issue tracker labeled `spec-errata`, citing a patch ID, before any re-opening.

**One caution to carry forward:** the strongest remaining risk in this plan is not any single technical item — it's M1's throughput gate. Run it early, on real spinning-disk-or-SSD hardware, before the architecture hardens around it. Everything else in this spec degrades gracefully via the drop order; performance doesn't.