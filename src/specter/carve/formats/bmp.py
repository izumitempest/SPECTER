"""BMP recovery — size-field clamp (§9.2).

Header ``42 4D``. The size field at offset 2 is frequently wrong in the wild,
so it is validated and clamped; when it cannot be trusted, recovery falls
back to the safety cap with a low-confidence flag.

Tasks: M1-2.
"""

from __future__ import annotations