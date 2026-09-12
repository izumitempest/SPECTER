# SPECTER — Offline Forensic Triage Platform

An educational reference implementation of core forensic techniques:
structural signature carving, type-aware entropy triage, evidence-integrity
verification, and tamper-evident audit logging. Built to be small and
readable enough that students can read it, modify it, and make real changes.

> **Not a production forensic suite.** Never run SPECTER on real casework,
> and never treat its outputs as evidence. Only synthetic and public corpora
> are used (§19 of the spec).

**Status:** specification frozen at `spec-v3.3`; implementation in progress
(M0 — baseline + vertical slice). See `docs/TASKS.md` for the task list and
`docs/changelog/` for a chronological record of every change.

## Documents

| File | What it is |
| --- | --- |
| `PROJECT.md` | The canonical, frozen specification (v3.3). |
| `docs/TASKS.md` | Milestone-by-milestone task list (M0–M6) with status. |
| `docs/IMPLEMENTATION.md` | Build order, global invariants, conventions. |
| `docs/changelog/` | One numbered, dated entry per material change. |
| `docs/TOUR.md` | Module map for students (teaching deliverable). |
| `docs/spec/` | Pre-merge spec history (patch spec, errata). |

## Quick start (development)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
specter --help          # or: python -m specter --help
pytest                  # default test set (excludes slow/bench)
```

Configuration lives in `.env` (see `.env.example`). The CLI is the M0
vertical slice: `init` → `image add` → `hash` → `carve` → `list`.

## Repository layout

```
src/specter/
  carve/      file carving: scanner, signature table, one parser per format (§9)
  integrity/  hash sidecar, Merkle tree, case manifest (§7)
  audit/      hash-chained audit log (§8)
  triage/     entropy analysis, keyword search, known-file sets (§10)
  jobs/       job orchestration: job table, worker pool (§4)
  store/      content-addressed blob store + garbage collection (§4.1)
  api/        FastAPI layer: auth, case-scoped authorization (§12)
  ui/         server-rendered Jinja2 templates + hex viewer (§11)
corpora/scripts/  seeded C1/C2/C3 corpus generators (§16.1)
tests/        unit (golden fixtures), property, fuzz, benchmarks (§17)
```

## License

MIT — a teaching tool that students may modify needs one. See `LICENSE`.