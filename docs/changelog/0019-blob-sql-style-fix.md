# 0019 — Gate-signal fixup: literalize INSERT in store/blob.py

- **Date:** 2026-09-27
- **Type:** fix
- **Spec refs:** §12 (L2 hook style rule: every `conn.execute` call reads as a
  single-line literal with `?` placeholders)

## Summary

Landed the mimosa stop-hook complaint for `store/blob.py:66`. The flagged
call was a tuple-bound parameter query already; execution wise it was safe.
The hook's regexp-style linter (L3 Native) reads single-line literals as
parameterized correctly but counts implicit string-concatenation as
mixing SQL text from runtime values. The fix is exclusively code style:
the SQL is now one string literal.

## What changed

- `src/specter/store/blob.py` — relevant `INSERT INTO blobs … ON CONFLICT`
  moved to a one-line SQL literal passed positionally.

## Verification

- `mimosa scan` on the file: 0 findings after the change.
- Local smoke-test of blob add/read path unchanged (no behavior change).