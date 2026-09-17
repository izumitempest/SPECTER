# 0012 — M0-9 + M0-10 done: scanner, signature registry, JPEG + PNG parsers

- **Date:** 2026-09-15
- **Type:** change
- **Spec refs:** §9.1 (windows), §9.2 (JPEG/PNG rows), §9.3 (total parsers),
  §9.4 (cursor), P-05, P-06, P-07, P-08, E-01, E-01+, E-06
- **Tag:** —

## Summary

Implemented the carving core. `scanner.py` runs the windowed single-pass
loop: sequential windows with a fixed 64-byte overlap, a fixed 512-byte
alignment filter, one cursor per job, and per-window candidate dispatch in
offset order. Rejected candidates never reach a cap-sized scan (P-07), and
the cursor skips recovered *and* attempted regions (P-08). Two parsers ship
with it: JPEG (the two-mode marker↔entropy state machine with E-01 fill
bytes and the E-01+ dangling-FF rule) and PNG (chunk walk with CRC-checked
first chunk as the O(1) rejection, later CRC failures truncate at the last
clean boundary, low-confidence).

## What changed

- `src/specter/carve/types.py` — new: `Recovery` shared record.
- `src/specter/carve/scanner.py` — `scan()` returning `ScanResult`
  (recoveries + `ScanStats`: elapsed, bytes, windows, O(1) rejections,
  recovered, masked_bytes).
- `src/specter/carve/signatures.py` — lazy registry of the signature table
  with `Signature` records (type, magic, parser, magic_delta) and the
  audit-recorded table version.
- `src/specter/carve/formats/jpeg.py` — marker/entropy state machine:
  APPn opaque walks (EXIF thumbnail never terminates), fill bytes, restart
  markers, progressive SOS re-entry, dangling-FF fallback, last-EOI-within-
  cap fallback, cap-bounding.
- `src/specter/carve/formats/png.py` — chunk walk, first-chunk CRC as the
  O(1) rejection, later CRC failure truncates low-confidence.
- `tests/unit/test_scanner.py` — 14 tests: both parsers on clean/thumbnail/
  fill-byte/restart-byte inputs, dangling FF, no-EOI fallback, bad first CRC
  rejects, later CRC truncates, alignment on/off, window seam, cursor
  masking, determinism, never-raise fuzz loop.

## Verification

Manual runs cover: EXIF thumbnail did not truncate; fill-byte and
restart-marker JPEGs recovered high-confidence; dangling FF and no-EOI hit
low-confidence fallbacks with a real last-EOI boundary; bad first PNG CRC
rejected O(1); a 512-aligned two-format image carved correctly across a
tiny 256-byte window (same result as a 1 MiB window); misaligned JPEG
rejected until alignment was disabled; same-image twice = same list.

## Next steps

- M0-11 (job manager + pool), M0-12 (CLI slice), M0-13 (security baseline):
  all pieces the CLI ties together.