"""ZIP (and OOXML) recovery — local-header walk with EOCD fallback (§9.2).

Header ``50 4B 03 04``. Walks local file headers. When stored sizes are zero
(streaming data descriptors), falls back to a backward scan from the end-of-
central-directory record ``50 4B 05 06``. The EOCD entry count is cross-
checked when available.

OOXML documents (docx/xlsx/pptx) are also ZIP containers; their refinement to
a specific type happens at loose-file import time via ``[Content_Types].xml``
(§10.2), not here — the carver reports them as ZIP.

Tasks: M1-1.
"""

from __future__ import annotations