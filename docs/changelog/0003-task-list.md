# 0003 — Task list: milestone-aligned plan (docs/TASKS.md)

- **Date:** 2026-09-11
- **Type:** change
- **Spec refs:** PROJECT.md §18 (milestones + drop order), §16.5 (recruiting
  note)
- **Tag:** —

## Summary

Wrote `docs/TASKS.md`, the authoritative task list driving the build. It
turns each of the six milestones in §18 into concrete, individually checkable
tasks (M0-1 … M6-4 plus four cross-cutting CX items), each annotated with the
spec section and patch/errata id that defines its acceptance. Three tasks are
already complete — repo init, the spec freeze, and the scaffold.

## What changed

- `docs/TASKS.md` — created. 47 tasks across M0–M6 and CX, each with an
  explicit spec reference and a `[ ]`/`[~]`/`[x]` status. Includes the exit
  criteria per milestone, the drop order pointer, and the recruiting note
  (study participants recruited at M2, not M5).
- `docs/changelog/README.md` — index updated.

## Verification

- Reviewed against §18: milestone names, week ranges, and exit criteria match
  the frozen spec; the two M1 gates (§9.5 throughput, P-09 density) are
  called out at week 4–5 as the spec requires.

## Next steps

- `docs/IMPLEMENTATION.md` — build order, global invariants, conventions, and
  the operationalised testing strategy.