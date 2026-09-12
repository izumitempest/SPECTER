"""GIF recovery — structural sub-block walk (§9.2, P-06).

Header ``47 49 46 38``. Parses the header and logical screen descriptor, then
walks image descriptors and length-prefixed sub-blocks until the trailer
``00 3B`` — which terminates correctly, unlike a naive scan for the first
``00 3B`` that appears inside LZW data.

Defensive rule (P-06): before each advance, bounds-check ``offset + size``
against both the safety cap and the image length. An overrun terminates with
a low-confidence flag instead of reading past the artifact.

Tasks: M1-1.
"""

from __future__ import annotations