"""Carving engine (§9).

Recovers files from raw images by walking their internal structure, not by
scanning for footer bytes. Layout:

- ``scanner``        — the windowed single-pass scan loop and cursor
- ``signatures``     — the 9-type signature table (maps magic → parser)
- ``mmap_accessor``  — read-only image access (POSIX/Windows)
- ``formats/``       — one parser module per supported type
"""

from __future__ import annotations