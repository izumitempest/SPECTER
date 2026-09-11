
# SPECTER-3 Consolidated Patch Specification

**Base document:** `PROJECT.md` (SPECTER-3 spec, v3)
**Patch levels:** v3.1 (review round 2) → v3.2 (round 3) → v3.3 (round 4)
**Status:** **FROZEN at v3.3.** Terminal patch level. See §Freeze Policy.

**How to apply:** each patch below carries an ID, a target section in `PROJECT.md`, an operation tag (`REPLACE` / `APPEND` / `AMEND`), and its source levels. Text is **final merged form** — where review rounds touched the same section (§4, §8, §10.3, §11/§12, §15), the merged text supersedes all previously circulated intermediate versions. Patches are order-independent.

## Version History

| Level | Source | Summary |
| --- | --- | --- |
| v3.1 | Round 2 | Chunk sidecar, case-scoped RBAC, lineage-preserving dedupe, canonical JSON, streaming search, disk-backed NSRL, auth lifecycle |
| v3.2 | Round 3 | JPEG state machine, O(1) rejection rule, density gate, cursor semantics, disk/quota/job locks, mutation fuzzing, study control condition |
| v3.3 | Round 4 | Transactional audit co-commitment, partial-chunk rule, regex bounds, blob GC + reconciliation, admin semantics, crash kill-test |

---

## Patches

### P-01 · §4 Architecture — operations model · APPEND · [v3.2, v3.3]

1. **Per-image job lock:** at most one active carve/hash job per image; concurrent submissions queue (default) or reject with a clear, audited error.
2. **Blob write protocol:** content is written to a temp path in the case directory, then `os.replace`d to its content-addressed name. Writer order: commit the Blob row, then rename. Readers never see partial blobs; concurrent writers of identical content converge safely. Only content-addressed names are ever GC-eligible — never temp-prefixed names.
3. **Disk management:** pre-job pre-flight (free space ≥ configurable multiple of image size, or per-case quota), re-checked every N artifacts; exhaustion stops the job cleanly, marks it `paused_disk`, and is audited. The verified-copy option requires 2× image size free before starting.
4. **Entropy profiles are stored aggregated** — head/tail/majority window statistics plus a histogram, never the full per-block series (~12.8K values per 50 MiB artifact; unaggregated across tens of thousands of artifacts is real DB bloat).
5. **Blob lifecycle — never delete inline.** Refcount decrements happen in transactions; physical deletion never occurs inside request/worker transactions. A GC job (periodic + on job completion) runs under `BEGIN IMMEDIATE`: select `refcount = 0`, unlink each file *inside* the transaction, delete rows, commit; unlink failure rolls back that row's deletion and is retried. Reconciliation runs both directions: files without rows are orphans from crashed writers (deleted); rows without files are flagged `lost`. **Backstop:** the blob store is a cache of the image's bytes; the image is the source of truth. Artifacts are deterministically re-derivable and verifiable against the chunk sidecar and manifest root — a lost blob costs a re-carve, never evidence.

### P-02 · §6 Evidence lifecycle — registration wording · AMEND · [v3.2]

Registration-by-path anchors hashes at registration; a later move or replacement is **detected at the next access or verification action and reported then** — no proactive filesystem monitoring. Registration records stat metadata (size, mtime, inode), compared at every open, catching moves and replacements cheaply before any re-hashing.

### P-03 · §7.1 Integrity — chunk hash sidecar · REPLACE · [v3.1, v3.3]

**Sidecar format:** `<image_id>.chunks` — a flat array of 32-byte SHA-256 values; `chunk_hash(i)` = bytes `[i·32, (i+1)·32)`. The DB stores the sidecar path, chunk size, and Merkle root. Rationale (corrected): flat-array layout gives O(1) leaf lookup, sequential write during the single acquisition pass, zero index machinery, and a trivially auditable format. (Row-per-chunk was workable — 262,144 rows ≈ 13–15 MB per TB imaged — the sidecar is simply simpler.) Sidecar integrity is committed by the root: tampered leaves produce proofs that fail against the anchored root. Optional `chunks_file_sha256` enables image-free sidecar self-checks.

**Partial trailing chunk:** the final chunk is hashed at its **exact remaining byte length, unpadded**; chunk count = `ceil(size / chunk_size)`; acquisition and verification use the identical rule, so artifacts in the final chunk verify like any other. Golden fixture: an image size deliberately not divisible by 4 MB.

### P-04 · §8 Audit log — serialization and write model · REPLACE · [v3.1, v3.3]

**(a) Canonical serialization (pinned):**

```python
entry_hash = SHA256(b"specter-audit-v1:" + json.dumps(
    payload, sort_keys=True, separators=(",", ":"),
    ensure_ascii=True, allow_nan=False).encode("utf-8"))
```

Payloads permit integers, strings, booleans, and null only — **no floats**. Timestamps are ISO-8601 strings; sizes are integers. The verification path calls exactly this function; CI round-trips serialize → hash → verify on Linux and Windows.

**(b) Metrics and the chain:** analytical measurements (entropy, confidence) live in the artifact and triage tables, referenced by ID — they do not enter the chain. Where a metric must appear in a payload: pinned-precision decimal string (`"7.4200"`, 4 dp) or a scaled integer with the scale in the field name (`confidence_bp: 85`).

**(c) Write model — transactional audit co-commitment.** Every entry describing a database state transition is inserted **in the same transaction as the transition it describes**. Workers buffer *payloads only* (unhashed, unsequenced); `seq`, `prev_hash`, and `entry_hash` are computed exclusively inside the `BEGIN IMMEDIATE` flush transaction, against the live tail. Case DB: WAL + `PRAGMA synchronous=FULL` (one fsync per ≤500-entry batch, amortized).

Consequences, stated in the writeup: (1) the chain's crash-consistency equals SQLite's — no committed transition lacks its entry, and no entry describes a transition that never committed; (2) a worker crash loses nothing that existed — the un-flushed batch's rows and entries vanish together, the supervisor audits the job failure, and deterministic re-running recovers the work; (3) export side-effects carry a milliseconds-scale crash window, documented, with manifest verification as reconciliation; (4) metrics stay out of the chain per (b).

**Rejected alternatives (recorded):** in-memory `multiprocessing.Queue` to a single writer (converts bounded contention into silent event loss; the writer dies with its queue); per-worker staging-file WAL (buys durability for events whose transitions would still be lost — co-commitment makes event durability identical to transition durability).

### P-05 · §9.1 Carving — window invariant · APPEND · [v3.1]

**Windows bound the scan pass, never the parsers.** All signature searches run per window on slices with a fixed 64-byte overlap (≥ longest signature, 16 B). Structural parsers read directly from the full read-only mapping and are bounded only by the safety cap and image length. A parser that consults window boundaries is a bug. The overlap must **not** be set to the safety cap: that re-scans ~40% of the image to solve a problem that cannot occur.

### P-06 · §9.2 Signature table — JPEG row · REPLACE · [v3.2]; GIF row validation · AMEND · [v3.1]

**JPEG — two-mode state machine.** *Marker mode:* markers are length-delimited; APPn/DQT/SOF/DHT consumed opaquely via length (an EXIF thumbnail's internal EOI cannot terminate the walk). SOS switches to *entropy mode*: `FF 00` = stuffed literal; `FF D0–D7` = restart marker; any other `FF xx` = real marker → return to marker mode; progressive JPEGs re-enter entropy mode at each subsequent SOS; `FF D9` in marker mode = EOI. No EOI within cap → fallback: last `FF D9` within cap, low-confidence; else cap-bounded. Validation: segment lengths bounds-checked. Implementation note: entropy-mode scanning costs ~4K Python iterations per MB (FF density ≈ 1/256), ~1–2 s/GB on JPEG-heavy images — profiled at the P-09 gate; a compiled regex matcher is the named optimization.

**GIF validation:** per sub-block, bounds-check `offset + size` against both the safety cap and the image length **before** advancing; overrun terminates with a low-confidence flag (instantiates the P-07 global rule for the most easily malformed format).

### P-07 · §9.3 Defensive parsing — rejection cost rule · APPEND · [v3.2]

Every candidate must be rejected in O(1) — alignment check, secondary signature (`PE\0\0`), first-chunk CRC (PNG), or a single bounds check — *before* any O(cap) structure or footer scan. A false positive that reaches a cap-sized scan is a performance bug, not load. Property tests enforce that no rejection path exceeds O(1) work.

### P-08 · §9.4 Overlap & dedup policy · REPLACE · [v3.1, v3.2]

**Deduplicate bytes, never records.** Every carved instance is its own `Artifact` row with its own offset, length, and confidence — each instance's location is evidence. Identical content is stored once via `content_sha256` → `Blob`. **Cursor semantics (pinned):** one global cursor shared by all signature searches; recovered *and attempted* regions — including cap-bounded low-confidence fallbacks — are skipped by all types; cross-type nesting is suppressed by policy (C3 ground truth marks nested instances expected-suppressed). The masking cost of cursor advance is **measured**: the evaluation reports the masking rate — known files lost inside fallback spans — alongside recall.

### P-09 · §9.5 Acceptance criteria — density gate · APPEND · [v3.2]

Clean-image throughput does not predict adversarial behavior; failures come from candidate density, and random bytes rarely produce aligned, structure-plausible candidates (~32 aligned `MZ` per GB of random data). The density corpus is the P-17 mutation fuzzer's output — valid fixtures with corrupted length/CRC/size fields — planted at aligned offsets at controlled densities (sweep 10³–10⁵ candidates/GB). Gate: effective throughput at 10⁴/GB must not fall below 50% of clean-image throughput. **Run at week 4–5, not week 8** — the one gate whose failure forces architectural change.

### P-10 · §10.1 Entropy — position windows · APPEND · [v3.2]

Directional checks are defined over block-position windows, not whole-artifact averages: the truncated/corrupt flag = tail-window entropy below the type's compressed-floor with a normal head. The signal depends on trailing foreign bytes — precision/recall is measured against §16.2's truncated-carve class, not assumed.

### P-11 · §10.3 Triage — search and hash sets · REPLACE · [v3.1, v3.3]

**Streaming search:** per-artifact mmap scanned in 1 MiB slices; literals via `bytes.find` (C-speed); regex via windowed `re.finditer`; memory O(window); findings are `TriageFinding` rows with byte offsets. FTS5 rejected: tokenization is wrong for binary artifacts and arbitrary regex. **Regex match-bound rule:** at query parse time, compute the pattern's maximum match length from the AST and reject unbounded patterns (`*`, `+`, `{n,}`) with an error explaining the forensic idiom (bounded context windows, e.g. `keyword.{0,200}` — unbounded quantifiers over binary data yield pathological matches). Reject computed maxima > 1 MiB. Scan overlap = computed maximum. Property test: boundary-spanning matches are found for every accepted pattern.

**Known-file hash sets, disk-backed:** NSRL-class lists are never loaded into RAM. An import command compiles a CSV once into a sorted binary array of 32-byte hashes (binary-search lookup, zero resident memory) plus an optional Bloom prefilter (~180 MB at 1% FP for 150M entries). A false "known" verdict suppresses an artifact from review — the asymmetric, harmful error — so Bloom hits are always confirmed by exact binary search before tagging.

### P-12 · §11/§12 Authorization & auth · APPEND · [v3.1, v3.2, v3.3]

**Case-scoped authorization:** `CaseMember(user_id, case_id, role_in_case)`. Every case-scoped endpoint resolves the resource's case and requires membership **or admin** before opening any file handle, via a FastAPI dependency (`require_case_access`) so the check is structurally impossible to omit from a new route. Cross-case access returns **404, not 403** (no existence oracle). **Admin semantics (normative):** admins bypass `CaseMember`; every audit entry records the actor's role, so admin cross-case access is visible in the trail, never silent.

**Auth lifecycle:** JWT secret generated once at deployment bootstrap (`specter init`, 256-bit, 0600 keyfile or env), persists across restarts; production fails fast if absent; access tokens expire (8 h default); argon2id pinned (`memory_cost=65536 KiB, time_cost=3, parallelism=1`).

**Transport and containment:** JWT in an httponly cookie + `SameSite=Lax` + double-submit CSRF token on every form (bearer/localStorage rejected — trades CSRF for XSS token theft); CSP headers set. Rate limiting: in-process token-bucket dependency on auth routes, named. Path containment: `os.path.realpath` + commonpath comparison at serve time (sibling-prefix and symlink escapes defeat naive prefix checks).

### P-13 · §15 Data model — consolidated deltas · REPLACE · [v3.1, v3.3]

| Change | Entity |
| --- | --- |
| Removed | `Chunk` |
| Added to `Image` | `chunks_path`, optional `chunks_file_sha256` |
| Added | `Blob(sha256 PK, storage_path, size, refcount, status)` — status: `active` / `lost` |
| Changed | `Artifact`: gains `content_sha256` (FK → Blob); no direct `storage_path`; per-instance `offset`, `length`, `confidence` retained |
| Added | `CaseMember(user_id, case_id, role_in_case)` |

`User`, `Case`, `Job`, `AuditEntry`, `Manifest`, `LooseFile`, `TriageFinding` unchanged from base v3 + v3.1.

### P-14 · §16.2 Triage evaluation · APPEND · [v3.2]

Per-type ROC/AUC reported with bootstrap confidence intervals and exact per-class counts; point estimates alone are noise at this set size.

### P-15 · §16.4 Resource comparison · APPEND · [v3.2]

Packaging: pip-install is primary; if PyInstaller is used for parity, **onedir mode** — onefile self-extracts to a temp directory on *every* launch, silently skewing time-to-first-artifact on every run. Disclosed either way.

### P-16 · §16.5 Teaching study · APPEND · [v3.2]

After the SPECTER modification task, each participant attempts a **timeboxed (30–45 min) comparable signature addition in PhotoRec's C source**; record success, time, a perceived-modifiability Likert, and prior Python/C experience as covariates. Fixed order (SPECTER first), order effects acknowledged; per-participant reporting; framed as indicative — no inferential statistics claimed at n=3–5.

### P-17 · §17 Testing · APPEND · [v3.2, v3.3]

- **Mutation-based fuzzing** alongside random-bytes: valid fixtures mutated in length, CRC, size, box-size, `e_lfanew`, and page-count fields, plus random bit flips. Invariants: never raise, never hang, every input terminates as recovery-or-rejection with a confidence flag. The mutated corpus **doubles as the P-09 density corpus**.
- **Golden fixtures:** image size not divisible by the chunk size (P-03); JPEG recipe via committed script — `cjpeg -restart` and `cjpeg -progressive` over public-domain images — deterministic, license-clean, covering the entropy-mode traps.
- **Zero-length images** are rejected at registration with an audit entry.
- **Crash-consistency test:** `SIGKILL` a worker mid-carve on a deterministic corpus at a fixed schedule, then assert: (1) every committed artifact row has its chain entry and vice versa; (2) the job is marked failed with a failure entry; (3) the blob directory reconciles with rows after GC; (4) re-running the job reproduces identical artifacts.

### P-18 · §18 Plan — drop order and M1 gate · AMEND · [v3.2]

Insert before the MP4/GIF demotion: "**JPEG structural walk → last-EOI-within-cap fallback** (APPn-opacity and alignment retained; recovers most real files; byte-exactness will differ — measured by the same fixtures)." M1 exit criteria: all nine types structural *or* demoted per drop order, with demoted fallbacks passing the same golden tests. Density gate runs week 4–5 (P-09).

---

## Rejected Prescriptions Register

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

## Corrected-Claims Register

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

## Freeze Policy

1. **v3.3 is terminal.** Merge P-01…P-18 into `PROJECT.md`, tag the result `spec-v3.3`, and freeze the document.
2. New findings go to the **issue tracker** labeled `spec-errata` and must cite a patch ID. Only security-relevant or claim-invalidating findings reopen the document.
3. **Next external review: M1 code + benchmark output, week 8** — JPEG golden tests, the P-09 density gate, and the P-17 kill test.
4. Open empirical questions, not answerable by further prose review: JPEG state machine vs. real-camera files; scan throughput at 10⁴ candidates/GB; student-study signal; AUC stability at small n.

---

Two usage notes: the two registers are the file's real long-term value — they're the immune system against re-litigating settled decisions under deadline pressure, yours or a reviewer's. And when you merge the patches into `PROJECT.md`, do it in one commit tagged `spec-v3.3` so the spec's own history is as traceable as the audit chain it describes. After that, the next artifact this project needs is M0's vertical slice, not another document.
