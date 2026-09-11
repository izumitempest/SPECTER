# 0004 — Fix CI lint failure (ruff I001, import order in entropy.py)

- **Date:** 2026-09-15
- **Type:** fix
- **Spec refs:** —
- **Tag:** —

## Summary

The first CI run (Linux + Windows matrix) failed at the **Lint (ruff)** step
with one error: `I001` in `src/specter/triage/entropy.py` — the import block
was unsorted. `import math` was placed after `from collections import
Counter`; ruff's isort rule requires the plain import first. One-line change,
and it matches ruff's own suggested fix exactly.

## What changed

- `src/specter/triage/entropy.py` — reordered the stdlib imports:

  ```python
  import math
  from collections import Counter
  ```

- `docs/changelog/README.md` — index updated.

## Verification

- The fix is exactly the reordering ruff itself prints in the CI log
  ("Organize imports" suggestion). Not re-run locally: system Python in this
  environment is broken for virtualenvs (`venv` links `bin/python` to the
  desktop launcher, so no `pip`), so no local ruff run was possible.
  **CI on push is the verifier** — watch the Lint step.

## Next steps

- If further lint/mypy issues surface in CI, fix them the same way (one
  changelog entry per fix).
- Continue with `docs/IMPLEMENTATION.md`, then M0-4 onward.