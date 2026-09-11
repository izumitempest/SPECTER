"""SPECTER — offline forensic triage platform (educational reference implementation).

This package implements the frozen specification in ``PROJECT.md`` (spec-v3.3):
structural file carving, type-aware entropy triage, evidence-integrity
verification, and a tamper-evident audit log.

The module map (also in docs/TOUR.md):

- ``specter.carve``        — carving engine (§9)
- ``specter.integrity``    — hashing, sidecar, Merkle tree, manifest (§7)
- ``specter.triage``       — entropy, keyword search, known-file sets (§10)
- ``specter.audit``        — hash-chained audit log (§8)
- ``specter.jobs``         — job orchestration and worker pool (§4)
- ``specter.store``        — content-addressed blob store + GC (§4.1)
- ``specter.api``          — FastAPI layer (auth, case-scoped access) (§12)
- ``specter.ui``           — server-rendered Jinja2 UI (§11)

Not a production forensic suite. Never run on real casework (§19).
"""

__version__ = "0.1.0"
__spec_version__ = "3.3"