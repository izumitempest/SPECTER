"""Read-only image access — a platform mmap accessor.

The image must never be writable through SPECTER (§6): POSIX uses
``PROT_READ``, Windows uses ``ACCESS_READ``. 64-bit address space is required
because the whole image is mapped read-only and demand-paged (§13).

Tasks: M0-6.
"""

from __future__ import annotations


class ReadOnlyImage:
    """A read-only, memory-mapped image (M0-6).

    Attributes:
        data: a read-only ``memoryview`` over the whole image.
        size: image length in bytes.
    """

    def __init__(self, data: memoryview, size: int) -> None:
        self.data = data
        self.size = size


def open_image(path: str) -> ReadOnlyImage:
    """Map ``path`` read-only (M0-6). Not yet implemented.

    Raises on 32-bit platforms (§13) and reports stat metadata at open (§6).
    """
    raise NotImplementedError("M0-6: open_image")