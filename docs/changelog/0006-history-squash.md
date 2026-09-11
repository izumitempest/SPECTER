# 0006 — History squashed into a single commit; `spec-v3.3` re-tagged

- **Date:** 2026-09-15
- **Type:** change
- **Spec refs:** §0 (freeze policy — the tag is preserved)
- **Tag:** `spec-v3.3` (re-pointed)

## Summary

The six early commits (spec import, spec merge/freeze, scaffold, task list,
ruff fix, implementation plan) were squashed into a **single commit** for a
clean, reviewable history. The `spec-v3.3` tag was re-pointed to that one
commit, so the freeze policy still holds: the frozen spec and everything
built on it live at the tagged commit. Nothing was pushed to a remote before
the squash, so no shared history was rewritten.

## What changed

- Git history: 6 commits → 1 commit (same tree, same content).
- `git tag spec-v3.3` moved to the new single commit.
- `docs/changelog/0001-*.md` — removed a now-stale commit-hash reference.
- This entry records the squash itself (CX-1 policy).

## Verification

- `git log --oneline` shows exactly one commit; `git show spec-v3.3` resolves
  to it and its tree contains all 72 project files.

## Next steps

- None. Future changes build on this single commit as normal, each with its
  changelog entry.