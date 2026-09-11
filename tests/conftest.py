"""Shared pytest fixtures.

The test suite is organised to match the spec's testing strategy (§17):

- ``unit/``      — golden-offset fixtures, one expected result per format
- ``property/``  — Hypothesis tests (Merkle, chain, O(1) rejection, regex)
- ``fuzz/``      — random-bytes + mutation fuzzing (never raise, never hang)
- ``benchmarks/``— §9.5 throughput targets and the P-09 density gate

Markers: ``slow`` (excluded by default), ``property``, ``fuzz``, ``bench``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the src tree importable even without an editable install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))