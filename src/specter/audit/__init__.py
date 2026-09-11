"""Hash-chained audit log (§8).

Maps to the claim "Audit chain detects editing and (bounded) deletion" (§2):

- ``chain``  — canonical serialization, genesis, O(n) verification
- ``writer`` — transactional co-commitment (the flush that keeps the chain
  consistent with the database)
"""

from __future__ import annotations