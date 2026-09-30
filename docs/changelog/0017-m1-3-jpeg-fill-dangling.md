# 0017 — M1-3 done: JPEG state machine complete (fill bytes, dangling FF, progressive)

- **Date:** 2026-09-27
- **Type:** change
- **Spec refs:** §9.2 (JPG row), P-06, **E-01** (JPEG fill bytes),
  **E-01+** (dangling FF), E-10 (entropy-mode cost note), §17 (golden
  fixtures per edge case)
- **Tag:** —

## Summary

Completed the JPEG two-mode state machine with the errata-driven fixtures.
The implementation already handled marker-mode / entropy-mode switching from
M0; this pass fills the three sharp edges pinned by ERRATA-001:

- **Fill bytes in entropy mode** (`FF FF` consume one, re-peek) —
  `tests/unit/test_scanner.py::TestJpeg.test_fill_bytes_before_marker`.
- **Dangling FF at cap/image end** treated as "no EOI found → low-confidence
  fallback" (never a marker parse) — `test_dangling_ff_falls_back`.
- **Progressive re-entry**: after an SOS and its entropy stretch, a second
  SOS flips back into entropy mode — `test_progressive_second_scan_resumes_entropy`.

APPn segments (incl. EXIF thumbnails) remain opaque, marker lengths are
bounds-checked, and restart markers `FF D0–D7` are consumed without
terminating the walk — all prior behavior retained.

## What changed

- `tests/unit/test_scanner.py` — three new edge-case fixtures added (the
  parser itself needed no changes; they now pin the intended behavior).
- `docs/changelog/` — this entry.

## Verification

Fresh sweep of the carving unit tests (jpeg, png, scanner, plus the new
format suites) passes 100%. The JPEG fixtures cover every trap §9.2 and
ERRATA-001 E-01/E-01+ name.

## Next steps

- M1-4: hard-nail P-07's O(1) rejection rule with property tests that assert
  rejection cost never exceeds constant work.