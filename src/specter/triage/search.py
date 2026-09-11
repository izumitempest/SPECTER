"""Streaming keyword/regex search over artifacts (§10.3, P-11, E-05).

Artifacts are scanned in 1 MiB slices so memory stays O(window). Literal
terms use ``bytes.find`` (C-speed); regexes use windowed ``re.finditer``.
Findings are stored as ``TriageFinding`` rows with byte offsets.

Regex length rules are deliberate and analytic, not arbitrary:

- **Bounded patterns** scan with overlap = their computed maximum match
  length (from the pattern's AST when available).
- **Unbounded patterns** (``*``, ``+``, ``{n,}``) are **accepted, not
  rejected**, and take the clamp path: a match ending at the window boundary
  is re-evaluated against an extension buffer, a hard 64 KiB cap applies, and
  matches that hit the cap are **flagged truncated** and surfaced to the
  analyst. The forensic idiom is a bounded context window (e.g.
  ``keyword.{0,200}``); unbounded quantifiers over binary data produce
  pathological matches.
- Patterns whose computed maximum exceeds the cap, or whose AST can't be
  analysed (``re._parser`` is semi-internal), also take the clamp path.

Tasks: M3-4, with property tests that unbounded patterns yield flagged
results and boundary-spanning matches are always found.
"""

from __future__ import annotations