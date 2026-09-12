"""Audit writer — transactional co-commitment (§8c, P-04c).

The rule that makes the audit chain trustworthy under crashes: an audit entry
describing a state transition commits **in the same transaction** as that
transition. Workers buffer payloads only (unhashed, unsequenced); ``seq``,
``prev_hash``, and ``entry_hash`` are computed inside the ``BEGIN IMMEDIATE``
flush transaction against the live chain tail.

Consequences (stated in the writeup):

1. Crash-consistency equals SQLite's — no committed transition lacks its
   entry, no entry describes a transition that never committed.
2. A worker crash loses nothing that existed — the un-flushed batch's rows
   and entries vanish together; deterministic re-run recovers the work.
3. Export side-effects carry a milliseconds-scale crash window, reconciled by
   manifest verification.
4. Metrics stay out of the chain (§8b).

Batching: one fsync per ≤500-entry batch (case DB runs ``synchronous=FULL``).

Tasks: M0-8 (append path), M2-5 (worker integration), M2-6 (job lifecycle
audit), M2-8 (kill test).
"""

from __future__ import annotations