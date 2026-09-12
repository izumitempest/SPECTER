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