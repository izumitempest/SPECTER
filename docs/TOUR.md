# SPECTER Tour — Module Map (draft)

Teaching deliverable (§11.4). Walks a student through the codebase: what each
package does, how a file gets from raw image to recovered artifact, and where
the integrity and audit guarantees live.

**Status:** stub. The full tour ships at M6-2, once the modules are
implemented. Until then, the module-level docstrings in `src/specter/` are the
authoritative map — each states its spec section and tasks.

## Where things live

| Package | What it does | Spec |
| --- | --- | --- |
| `specter.carve` | Finds files in a raw image by walking their structure | §9 |
| `specter.integrity` | Hashes, chunk sidecar, Merkle tree, case manifest | §7 |
| `specter.audit` | Hash-chained, tamper-evident log of every action | §8 |
| `specter.triage` | Entropy triage, keyword search, known-file sets | §10 |
| `specter.jobs` | Persisted jobs and the worker pool | §4 |
| `specter.store` | Content-addressed blobs + garbage collection | §4.1 |
| `specter.api` | FastAPI: auth and case-scoped access | §12 |
| `specter.ui` | Server-rendered Jinja2 UI + hex viewer | §11 |

## The lifecycle of a file

1. **Register** an image (`specter image add`) — anchored by hashing (§6).
2. **Hash** (`specter hash`) — one pass, whole-image + chunk sidecar (§7).
3. **Carve** (`specter carve`) — the scanner finds files (§9).
4. **Triage** — entropy and search help the analyst focus (§10).
5. **Verify** — the audit chain and manifest prove nothing changed (§7, §8).