"""PDF recovery — scan to the *last* %%EOF within cap (§9.2, §9.3).

Header ``25 50 44 46`` (``%PDF-``). PDF files are incrementally updated by
appending, so the trailer lives at the end: we scan the whole window and take
the *last* ``%%EOF``, not the first. Malformed files without an EOF degrade
to low-confidence cap-bounded recovery — never raise.

Embedded PDFs (still ``%PDF`` headers deep in another file's data) are
handled by the scanner's outermost-first policy — we don't special-case them
here.

Tasks: M1-2.
"""

from __future__ import annotations

from specter.carve.types import Recovery

SIGNATURE = b"%PDF-"
_EOF = b"%%EOF"


def parse(buf: bytes, offset: int, cap: int) -> Recovery | None:
    size = len(buf)
    limit = min(offset + cap, size)
    if offset + 5 > limit or bytes(buf[offset : offset + 5]) != SIGNATURE:
        return None

    # Scan for every %%EOF within the window; take the LAST one (incremental
    # saves append trailers; the newest one is the true parent trailer).
    last = buf.rfind(_EOF, offset, limit)
    if last == -1:
        # No EOF — truncated or garbage; report up to cap, low confidence.
        return Recovery("pdf", offset, limit - offset, "low")
    end = last + len(_EOF)
    return Recovery("pdf", offset, end - offset, "high")