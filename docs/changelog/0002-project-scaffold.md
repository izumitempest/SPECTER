# 0002 — Project scaffold: file tree, packaging, CI, module stubs

- **Date:** 2026-09-11
- **Type:** change
- **Spec refs:** §4 (module map), §11 (documents), §12 (secrets/.env), §17
  (testing layout), Appendix A (tech stack)
- **Tag:** —

## Summary

Created the repository skeleton for the M0 baseline. The goal is a structure
that (a) mirrors the spec's module map so each file has an obvious home, (b)
is importable and CI-ready from the first commit, and (c) carries the pinned
design decisions as module docstrings so nobody re-litigates them while
implementing. No engine logic is written yet — modules are stubs that state
their contract, spec section, and owning task.

## What changed

- **Packaging/config** — `pyproject.toml` (setuptools src-layout, the
  dependency set from Appendix A, dev extras, `specter` console script,
  pytest markers, ruff + mypy strict) · `.gitignore` · `.env.example`
  (documented `SPECTER_*` keys) · `LICENSE` (MIT) · `README.md`.
- **CI** — `.github/workflows/ci.yml`: Linux + Windows matrix, Python 3.11
  and 3.12, ruff → mypy → pytest (slow/bench excluded).
- **Source tree (`src/specter/`)** — the eight spec modules each as a package:
  `carve` (scanner, signatures, mmap_accessor, `formats/` with one module per
  type), `integrity` (hashing, sidecar, merkle, manifest), `audit` (chain,
  writer), `triage` (entropy, search, known), `jobs` (manager, pool),
  `store` (blob, gc), `api` (app, auth, deps), `ui`. Plus `config.py`,
  `db.py`, `cli.py` (stubbed M0 vertical slice), `__init__.py`, `__main__.py`.
- **Testing tree** — `tests/conftest.py`, `tests/test_smoke.py`, and
  `unit/`, `property/`, `fuzz/`, `golden/fixtures/`, `benchmarks/` stubs.
- **Docs** — `docs/TOUR.md` (module map, draft), `docs/labs/README.md`
  (four exercises), `corpora/README.md` (C1–C3 plan).
- **Housekeeping** — removed tool-state dirs (`.v2c/`, `.mimosa/`) from git
  tracking; added them to `.gitignore`.

## Verification

- Import/CLI smoke test and CI config are in place but the dependency
  environment was not installed in this session; the smoke test runs in CI on
  the Linux + Windows matrix.

## Next steps

- `docs/TASKS.md` (the milestone task list) and `docs/IMPLEMENTATION.md`
  (build order, invariants, conventions).
- Then M0-4 onward: `config.py`, `db.py`, the mmap accessor, hashing, the
  audit chain, the scanner, and the CLI vertical slice.