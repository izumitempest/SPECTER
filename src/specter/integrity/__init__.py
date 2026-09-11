"""Integrity layer (§7) — hashing, chunk sidecar, Merkle tree, manifest.

Maps to the claim "Integrity layer detects tampering" (§2): whole-image
hashing detects change, the chunk sidecar localises it, the Merkle root
compresses it into one 32-byte value for out-of-band anchoring, and the
manifest ties it all together.
"""

from __future__ import annotations