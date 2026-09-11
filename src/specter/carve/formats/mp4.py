"""MP4/MOV recovery — box-chain walk (§9.2).

``ftyp`` sits at offset 4; the box starts four bytes before the match. The
walk chains box sizes, handling both edge cases: size 0 means "extends to
end of file" and size 1 means "a 64-bit largesize follows". ``ftyp``-first is
assumed. The box chain is bounds-checked throughout.

Tasks: M1-2.
"""

from __future__ import annotations