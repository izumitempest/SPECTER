"""The windowed single-pass scan loop, cursor, and candidate policy.

Spec: §9.1, §9.3, §9.4.

Design rules pinned in the spec — do not "simplify" these away:

- **Windows bound the scan pass, never the parsers.** The scan reads
  sequential windows (default 128 MiB) with a fixed 64-byte overlap. Parsers
  read the full read-only mapping and are bounded only by the safety cap.
  A parser that consults window boundaries is a bug (P-05).
- **Sector alignment filter** rejects most garbage in O(1) before any scan
  (default 512, configurable to 4096 or off).
- **One cursor per carve job.** Recovered *and* attempted regions — including
  cap-bounded fallbacks — are skipped (P-08). The scan loop is sequential in
  one worker; the pool parallelises across jobs and, within a job, chunk
  hashing and triage only (E-06).
- **Masking is measured, not assumed:** the scanner counts known-file losses
  inside skipped spans and reports the masking rate (§9.4).
- **Parsers are total:** every candidate resolves to a recovery or a
  rejection with a confidence flag — never an exception, never a hang (§9.3).

Tasks: M0-9 (loop skeleton), M1-4 (O(1) rejection + totality), M1-5
(cursor + masking counter).
"""

from __future__ import annotations


def scan(image: object, table_version: int = 1) -> list[object]:
    """Run the whole carving pass (M0-9). Not yet implemented.

    Returns a list of recovered artifact candidates. Deterministic: the same
    image always yields the same list (§17).
    """
    raise NotImplementedError("M0-9: scan")