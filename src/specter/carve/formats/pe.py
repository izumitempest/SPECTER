"""EXE/PE recovery — ``MZ`` accepted only with a valid PE header (§9.2).

Header ``4D 5A`` is only two bytes and produces enormous false-positive
volume, so recovery is accepted **only if** ``e_lfanew`` is in bounds and
``PE\\0\\0`` validates at that offset. Size is the maximum of the sections'
``PointerToRawData + SizeOfRawData`` plus the headers.

The O(1) rejection rule (P-07) is load-bearing here: a ``MZ`` at an aligned
offset with an out-of-bounds ``e_lfanew`` or a missing PE signature must be
discarded immediately, never entering a cap-sized scan.

Tasks: M1-2.
"""

from __future__ import annotations