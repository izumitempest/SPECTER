"""Content-addressed blob store (§4.1.2, E-04, §15).

Every carved instance is its own ``Artifact`` row (its location is evidence),
but identical bytes are stored only once, named by ``content_sha256`` and
tracked in the ``Blob`` table.

Write protocol, pinned:

1. Content is written to a temp path ``<job_id>_<uuid>.tmp`` in the case dir.
2. The worker's flush batch commits artifact rows + blob rows + audit entries
   in **one transaction**, then renames the temp file to its content-addressed
   name **after** commit.
3. Materialization check: row + file exist → skip; row exists, file missing →
   re-materialise; new row → temp, commit, rename.
4. Readers never see partial blobs. A reader hitting a missing file with an
   ``active`` row retries briefly (5 × 20 ms) to ride out the commit→rename
   window; persistent absence is ``lost`` and surfaced — readers never
   repair.

Tasks: M1-6 (writer path), M2-5 (integration).
"""

from __future__ import annotations