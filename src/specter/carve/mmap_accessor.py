"""Read-only image access — the platform mmap accessor.

Spec: §6 (SPECTER never opens an image writable — this accessor is the only
way in, and it is always read-only), §9.1 (POSIX ``PROT_READ`` / Windows
``ACCESS_READ``), §13 (64-bit required; the whole image is demand-paged, so
mapping images larger than RAM is safe).

Registration stat metadata (size, mtime, inode) is captured at every open so
a moved or replaced image is caught cheaply before any re-hashing (P-02).
Zero-length images are refused here and at registration (§17).
"""

from __future__ import annotations

import mmap
import os
import struct
from dataclasses import dataclass


class ImageOpenError(RuntimeError):
    """The image cannot be opened (32-bit platform, missing, or empty)."""


@dataclass(frozen=True)
class ImageStat:
    """File metadata captured at open time (P-02: size, mtime, inode)."""

    size: int
    mtime_ns: int
    inode: int


class ReadOnlyImage:
    """A read-only memory-mapped image. Use as a context manager."""

    def __init__(self, mm: mmap.mmap, stat: ImageStat) -> None:
        self._mm = mm
        self.stat = stat
        self.size = stat.size

    @property
    def data(self) -> mmap.mmap:
        """The read-only mapping (supports slicing and ``bytes()``)."""
        return self._mm

    def close(self) -> None:
        self._mm.close()

    def __enter__(self) -> ReadOnlyImage:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def open_image(path: str | os.PathLike[str]) -> ReadOnlyImage:
    """Map ``path`` read-only and return it with its stat metadata.

    Raises ImageOpenError on a 32-bit platform, a missing file, or a
    zero-length image (§17: rejected at registration).
    """
    if struct.calcsize("P") * 8 < 64:
        raise ImageOpenError("SPECTER requires a 64-bit platform (spec §13)")

    st = os.stat(path)
    if st.st_size == 0:
        raise ImageOpenError(f"Zero-length image refused: {path} (spec §17)")

    fd = os.open(path, os.O_RDONLY)
    try:
        if os.name == "posix":
            mapping = mmap.mmap(fd, 0, prot=mmap.PROT_READ)
        else:
            mapping = mmap.mmap(fd, 0, access=mmap.ACCESS_READ)
    finally:
        os.close(fd)

    return ReadOnlyImage(
        mapping,
        ImageStat(size=st.st_size, mtime_ns=st.st_mtime_ns, inode=st.st_ino),
    )