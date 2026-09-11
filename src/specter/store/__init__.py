"""Content-addressed blob store + garbage collection (§4.1, §15).

- ``blob`` — writes carved artifacts to the filesystem under case dirs
- ``gc``   — two-phase garbage collection and reconciliation
"""

from __future__ import annotations