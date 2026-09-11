"""SQLite recovery — page-integer validation (§9.2).

Signature is the 16-byte header ``SQLite format 3\\0``. Page size lives at
offset 16 (the value 1 means 65536), page count at offset 28; size = pages ×
page size. Both fields are validated. Stale or implausible page counts are
flagged and the recovery falls back to the safety cap.

Module is named ``sqlite_fmt`` (not ``sqlite``) to avoid any shadowing of the
stdlib ``sqlite3`` import in the same package.

Tasks: M1-2.
"""

from __future__ import annotations