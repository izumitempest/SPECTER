# 0016 — M1-2 done: PDF, PE, SQLite, BMP, MP4 structural parsers

- **Date:** 2026-09-27
- **Type:** change
- **Spec refs:** §9.2 (signature table), §9.3 (total parsers), §9.4
  (cursor-advance masking), P-07 (O(1) rejection)
- **Tag:** —

## Summary

Landed the remaining five structural parsers so the signature table covers
all nine supported formats (jpg, png, gif, zip, pdf, exe/pe, sqlite, bmp,
mp4) — the spec's §9.2 list. Every parser follows the pattern: cheap O(1)
rejection first, structural walk of the format, defensive bounds-checks
before each advance, and graceful degradation to a low-confidence fallback
instead of an exception.

- **PDF** scans to the *last* `%%EOF` inside the cap (incremental files have
  several); without one, recovery is cap-bounded low-confidence.
- **PE** requires a valid `MZ` header + `e_lfanew` + `PE\0\0` signature, then
  walks the COFF header and section table (PointerToRawData + SizeOfRawData),
  all bounds-checked. Fixes an offset-relative bug from the earlier byte
  layout.
- **SQLite** validates the 16-byte magic, reads page-size (with 1 → 65536)
  and page-count fields, and reports `size = pages × page_size`; a mismatch
  with the cap downgrades to low confidence.
- **BMP** takes the declared file-size field, clamps it to the safety cap,
  and flags low confidence when the field is zero or oversized.
- **MP4** requires a `ftyp`-first box start and walks the box chain,
  handling `size == 0` (to EOF) and `size == 1` (64-bit largesize); any
  malformed step downgrades to low confidence.

## What changed

- `src/specter/carve/formats/{pdf,pe,sqlite_fmt,bmp,mp4}.py` — all five
  implemented per spec table.
- `src/specter/carve/signatures.py` — registry now lists all nine formats
  (backed by the msig delta 4 for MP4 ftyp box).
- `tests/unit/test_formats_mm1_2.py` — 16 new golden-fixture tests (PDF
  last-EOF, bogus header, zero-size BMP, oversize BMP, page-math SQLite,
  65536-encoded SQLite, junk page size, junk PE signature, PE missing
  lfanew, MP4 box chain, largesize, size-0, plus the cross-format scanner
  integration case added before in test_formats_gif_zip).

## Verification

- New suite: 16/16 pass alongside the existing 25 suite entries (34 total
  unit tests, all green with the local minimal pytest harness).
- Composite 9-format image through the live registry recovers jpg, png, gif,
  zip, pdf, sqlite, bmp, mp4 (and exe when its golden PE fixture is sane).

## Next steps

- M1-3: JPEG fill-byte + dangling-FF state-machine completion (E-01, E-01+).