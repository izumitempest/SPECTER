"""PDF recovery — scan to the last ``%%EOF`` (§9.2).

Header ``25 50 44 46``. Incremental saves produce several ``%%EOF`` markers,
so recovery scans to the *last* one within the safety cap. Embedded PDFs are
handled by the scanner's outermost-first policy.

Tasks: M1-2.
"""

from __future__ import annotations