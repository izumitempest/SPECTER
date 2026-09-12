"""Case integrity manifest — export and verify (§7.3).

The manifest is the out-of-band anchor. It contains: case ID, per-image
whole-image SHA-256 and Merkle root, the audit chain head hash + sequence
number, tool version, and a UTC timestamp.

Honest limits, stated publicly (not just in the spec): interior edits to the
image or audit chain are always detectable; suffix deletion is detectable
only back to the last exported manifest; the manifest is tamper-evidence
against corruption and casual tampering — not non-repudiation, and not proof
against an attacker who held both database and image before any export.

Tasks: M2-4.
"""

from __future__ import annotations