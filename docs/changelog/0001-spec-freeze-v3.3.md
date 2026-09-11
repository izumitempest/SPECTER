# 0001 — Spec merged and frozen at v3.3

- **Date:** 2026-09-11
- **Type:** milestone
- **Spec refs:** PROJECT.md §0 (freeze policy); P-01…P-18; ERRATA-001 (E-01…E-10 and continuations)
- **Tag:** `spec-v3.3`

## Summary

The three pre-merge spec documents — the base v3 spec (`PROJECT.md`), the
consolidated patch specification v3.1–v3.3 (`PATCH.md`), and `ERRATA-001` —
were merged into a single canonical `PROJECT.md` and frozen at v3.3,
satisfying the §0 freeze policy ("merge P-01…P-18 into PROJECT.md, tag the
result `spec-v3.3`"). The project is now at its first git tag and the spec is
closed to prose changes; further findings go to the issue tracker as
`spec-errata`.

## What changed

- `PROJECT.md` — rewritten as the merged canonical spec. Base v3 text with
  P-01…P-18 folded in place: new §0 Freeze Policy; §4.1 operations model
  (per-image job lock, blob write protocol, disk pre-flight, aggregated
  entropy profiles, two-phase blob GC); §6 registration/stat-metadata
  wording; §7.1 chunk-hash sidecar + partial-trailing-chunk rule + pinned
  Merkle construction; §8 pin-based canonical serialization, metrics-out
  rule, and transactional audit co-commitment; §9.1 window invariant; §9.2
  JPEG two-mode state machine + GIF overrun rule; §9.3 O(1) rejection rule;
  §9.4 dedupe-bytes-not-records + cursor semantics; §9.5 density gate; §10.1
  position windows; §10.3 streaming search + regex clamp path; §12
  case-scoped authorization, auth lifecycle, transport/containment; §15
  Blob/CaseMember data model; §16.2/16.4/16.5 evaluation additions; §17
  mutation fuzzing + kill test; §18 drop-order and M1 exit criteria
  amendments. ERRATA items applied inline (JPEG fill bytes, dangling FF,
  two-phase GC, pinned Merkle shape, retry-before-lost, single-API-process
  constraint, seq-order semantics). Added Appendices C and D (rejected
  prescriptions, corrected claims) merged from the patch spec, including the
  errata's register additions.
- `PATCH.md` → `docs/spec/PATCH-v3.1-v3.3.md` (moved, content unchanged —
  provenance history).
- `PATCH_AMEND.md` → `docs/spec/ERRATA-001.md` (moved, content unchanged).
- `docs/changelog/README.md` + `docs/changelog/0001-…md` — changelog
  practice adopted (policy CX-1): every material change ships with a dated,
  numbered entry.
- `git init` on `main`; original three documents preserved in the root
  commit (49dab8c).

## Verification

- `git show spec-v3.3` — the tag commit contains exactly the spec merge, the
  two moved provenance docs, and the changelog.
- Cross-checked each patch ID (P-01…P-18) and errata item (E-01…E-10 +) against
  the merged text; REPLACE/AMEND targets (§7.1, §8, §9.2, §9.4, §10.3, §15,
  §17, §18) verified old text is superseded, not duplicated.

## Next steps

- M0 scaffold: file tree, packaging (`pyproject.toml`), build tooling, CI.
- `docs/TASKS.md` (milestone task list) and `docs/IMPLEMENTATION.md` (build
  order, invariants, conventions).