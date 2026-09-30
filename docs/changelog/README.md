# Changelog

Every material change to SPECTER — milestone, patch, fix, or configuration
decision — is recorded here as a numbered entry, in **chronological order**.
This is project policy (task CX-1): a commit that contains a material change
also contains its changelog entry.

## Format

One directory entry per change: `NNNN-slug.md` — zero-padded sequence number
(the chronological order; never reused) plus a short kebab-case slug.

Each entry has this front matter:

- **Date** — ISO-8601 UTC.
- **Type** — `milestone` (an M0–M6 milestone completes) · `patch` (spec /
  patch-level decision) · `change` (implementation or configuration change) ·
  `fix`.
- **Spec refs** — PROJECT.md sections / patch IDs (P-xx) / errata (E-xx) /
  issue IDs this entry touches, or `—`.
- **Tag** — git tag marking this point, if any.

Body: **Summary** (one paragraph: what happened and why), **What changed**
(files touched, spec sections), **Verification** (how it was checked), and
**Next steps**.

The index table below is updated in the same commit as the entry it lists.

## Index

| # | Date | Type | Title | Tag |
|---|---|---|---|---|
| 0001 | 2026-09-11 | milestone | Spec merged and frozen at v3.3 | `spec-v3.3` |
| 0002 | 2026-09-11 | change | Project scaffold: file tree, packaging, CI, module stubs | — |
| 0003 | 2026-09-11 | change | Task list: milestone-aligned plan (docs/TASKS.md) | — |
| 0004 | 2026-09-15 | fix | CI lint failure: import order in entropy.py (ruff I001) | — |
| 0005 | 2026-09-15 | change | Implementation plan (docs/IMPLEMENTATION.md) | — |
| 0006 | 2026-09-15 | change | History squashed to one commit; `spec-v3.3` re-tagged | `spec-v3.3` |
| 0007 | 2026-09-15 | change | M0-4 done: config loader (env + .env, production fail-fast) | — |
| 0008 | 2026-09-15 | change | M0-5 done: SQLite schema v1 and connection layer | — |
| 0009 | 2026-09-15 | change | M0-6 done: read-only mmap accessor | — |
| 0010 | 2026-09-15 | change | M0-7 done: acquisition hashing + chunk sidecar | — |
| 0011 | 2026-09-15 | change | M0-8 done: hash-chained audit log | — |
| 0012 | 2026-09-15 | change | M0-9/M0-10: scanner, signature table, JPEG + PNG parsers | — |
| 0013 | 2026-09-15 | change | M0-11 done: job manager + pool | — |
| 0014 | 2026-09-24 | change | M0-12/13/14 landed; gate handled via verified false-positive path | — |
| 0015 | 2026-09-27 | change | M1-1 done: GIF + ZIP structural parsers registered | — |
| 0016 | 2026-09-27 | change | M1-2 done: PDF + PE + SQLite + BMP + MP4 structural parsers | — |
| 0017 | 2026-09-27 | change | M1-3 done: JPEG fill bytes, dangling FF, progressive SOS | — |