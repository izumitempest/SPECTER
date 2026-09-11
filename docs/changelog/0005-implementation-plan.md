# 0005 — Implementation plan (docs/IMPLEMENTATION.md)

- **Date:** 2026-09-15
- **Type:** change
- **Spec refs:** §5, §9, §17, §18 (build order, invariants, gates)
- **Tag:** —

## Summary

Wrote `docs/IMPLEMENTATION.md` — the "how we build" companion to
`docs/TASKS.md`. It sets the build order (bottom-up, CLI-first), lists the 15
global invariants every change must respect (the pinned rules from the spec:
total parsers, O(1) rejection, the 64-byte overlap, cursor semantics,
canonical audit serialization, co-commitment, the pinned Merkle tree, blob
write protocol, 404-not-403, single API process, and the rest), and
operationalises the testing strategy against the test directories.
Conventions (mypy strict, ruff, naming, ranges, changelog discipline) and the
two architectural gates (§9.5 throughput and the P-09 density gate at
week 4–5) close the document.

## What changed

- `docs/IMPLEMENTATION.md` — created.
- `docs/changelog/README.md` — index updated.

## Verification

- Cross-checked every invariant against the frozen spec (each carries its
  section or patch/errata reference).
- Confirmed the gates and the drop order match §18.

## Next steps

- Begin M0-4 (`config.py`) onward; CI (after the 0004 fix) is the verifier.