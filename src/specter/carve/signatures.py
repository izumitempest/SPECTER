"""The signature table — the registry of supported format parsers (§9.2).

Maps each format's header magic to its structural parser. Header bytes are
the cheap trigger; the parser's own validation does the real work, and every
candidate must be rejected in O(1) before any expensive scan (P-07).

The signature-table version is included in the audit config snapshot (§8),
so a change here that alters carving results is traceable.

| Type | Header | Parser module |
| --- | --- | --- |
| JPG | ``FF D8 FF`` | ``formats.jpeg`` |
| PNG | 8-byte signature | ``formats.png`` |
| GIF | ``47 49 46 38`` | ``formats.gif`` |
| PDF | ``25 50 44 46`` | ``formats.pdf`` |
| ZIP | ``50 4B 03 04`` | ``formats.zip`` |
| EXE | ``4D 5A`` | ``formats.pe`` |
| SQLite | ``SQLite format 3\\0`` | ``formats.sqlite_fmt`` |
| BMP | ``42 4D`` | ``formats.bmp`` |
| MP4 | ``ftyp`` at +4 | ``formats.mp4`` |

Tasks: M0-9 (registry), M1-1/M1-2 (parser implementations).
"""

from __future__ import annotations

#: Signature-table version, audited via the config snapshot (§8).
SIGNATURE_TABLE_VERSION = 1