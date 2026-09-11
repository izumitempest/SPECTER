"""PNG recovery — chunk walk with CRC validation (§9.2).

Recovers by walking chunks: length + type + data + CRC, ending at ``IEND``.
CRC validation gives PNG the best false-positive rejection in the signature
table. The first chunk's CRC is checked in O(1) as the cheap rejection before
any longer scan (P-07).

Tasks: M0-10 (golden fixtures, incl. a bad-CRC file that must be rejected),
M1-1.
"""

from __future__ import annotations