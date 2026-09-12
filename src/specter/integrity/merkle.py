"""Merkle tree — pinned construction (E-03).

The tree shape is pinned because the root is exported out-of-band and any
re-derivation (third parties, ports, future versions) must compute the same
value:

- Parents are ``SHA256(left ‖ right)`` over fixed-width 32-byte inputs.
- A level with an odd node count > 1 duplicates the final node
  (``SHA256(n ‖ n)``).
- A single leaf's root **is** the leaf hash itself.

Provides ``root(leaves)``, ``proof(leaves, index)``, and
``verify(root, leaf, proof)`` (O(log n)).

Tasks: M2-1, with fixtures for an odd chunk count, a partial trailing chunk,
and a sub-chunk-size image (n = 1).
"""

from __future__ import annotations