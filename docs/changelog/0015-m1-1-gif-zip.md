# 0015 — M1-1 done: GIF + ZIP structural parsers registered

- **Date:** 2026-09-27
- **Type:** change
- **Spec refs:** §9.2 (signature table), §9.3 (total parsers), P-06 (GIF
  defensive bounds-check), P-07 (O(1) rejection), §18 M1 exit criteria
- **Tag:** —

## Summary

Added the first two structural format parsers of M1 — GIF (length-prefixed
sub-block walk) and ZIP (local-header walk with EOCD fallback) — and
registered them in the signature table so `specter carve` now recognizes four
formats end-to-end (jpg, png, gif, zip).

GIF parser: header → 6-byte logical screen descriptor → per-image
descriptor with local color table sizing → length-prefixed sub-block walk.
Bounds are checked before every advance (P-06); stray `00 3B` inside
sub-block payloads cannot end the parse; overruns degrade to
low-confidence recovery of whatever walked cleanly (§9.3).

ZIP parser: little-endian local file header walk with a proper EOCD check
(`PK\x05\x06` must terminate; count match enforced when walkable). Streaming
records (zero sizes + 0x08 flag) fall into the EOCD fallback instead of
failing, and a bad first header rejects in O(1) (P-07).

## What changed

- `src/specter/carve/formats/gif.py` — structural GIF walker.
- `src/specter/carve/formats/zip.py` — structural ZIP walker.
- `src/specter/carve/signatures.py` — registers gif + zip alongside jpeg/png.
- `tests/unit/test_formats_gif_zip.py` — 9 golden-fixture tests:
  minimal/nested/truncated GIF; two-record + streaming + bogus + fallback ZIP;
  scanner end-to-end sees all four types on a composite image.

## Verification

- Hand-built fixtures pass every case (clean parse with confidence flags,
  premature-`00 3B` inside a GIF sub-block never terminates, bogus header
  rejects, ZIP fallback lands mid-stream).
- CLI regression: register → hash → carve → list on the demo image still
  returns the two planted JPEG/PNG artifacts, audit chain intact.

## Next steps

- M1-2: remaining five formats (pdf, pe, sqlite, bmp, mp4).