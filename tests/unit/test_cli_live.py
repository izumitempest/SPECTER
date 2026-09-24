"""Integration tests for the M0 vertical slice (§18 M0 exit; §16.7).

init → image add → hash → carve → list, and the determinism invariant
(same image carved twice → identical artifact set, per §17).
"""

from __future__ import annotations

import sys
import zlib
from pathlib import Path

import pytest

from specter.audit.writer import verify
from specter.db import connect


def _png() -> bytes:
    def chunk(t: bytes, d: bytes) -> bytes:
        return (
            len(d).to_bytes(4, "big")
            + t
            + d
            + (zlib.crc32(t + d) & 0xFFFFFFFF).to_bytes(4, "big")
        )

    ihdr = chunk(b"IHDR", (1).to_bytes(4, "big") * 2 + b"\x08\x06\x00\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + ihdr + chunk(b"IDAT", zlib.compress(b"\x00" * 64)) + chunk(b"IEND", b"")


def _jpeg() -> bytes:
    return (
        b"\xff\xd8\xff"
        + b"\xff\xe0" + (6).to_bytes(2, "big") + b"abcd"
        + b"\xff\xda" + (5).to_bytes(2, "big") + b"\x01\x00\x00"
        + b"\x10" * 32
        + b"\xff\xd9"
    )


def _run(cli_args: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    """Invoke the CLI with SPECTER_DATA_DIR pointed at tmp_path."""
    monkeypatch.setenv("SPECTER_DATA_DIR", str(tmp_path / "data"))
    from specter.cli import main

    return main(cli_args)


def test_vertical_slice_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    image = tmp_path / "exhibit.dd"
    pad = (512 - (512 + len(_jpeg())) % 512) % 512
    image.write_bytes(b"\x00" * 512 + _jpeg() + b"\x00" * pad + _png())

    assert _run(["init"], tmp_path, monkeypatch) == 0
    assert _run(["image", "add", "default", str(image)], tmp_path, monkeypatch) == 0
    assert _run(["hash", "default", "1"], tmp_path, monkeypatch) == 0
    assert _run(["carve", "default", "1"], tmp_path, monkeypatch) == 0
    assert _run(["list", "artifacts", "--case", "default"], tmp_path, monkeypatch) == 0

    conn = connect(str(tmp_path / "data" / "specter.db"))
    rows = conn.execute("SELECT type, offset, length FROM artifacts ORDER BY id").fetchall()
    assert [(r[0], r[1]) for r in rows] == [("jpg", 512), ("png", 1024)]
    report = verify(conn, 1)
    assert report.ok, f"audit chain broken: {report.detail}"
    assert report.entries >= 4  # registration + hash + ≥2 artifact recoveries
    conn.close()


def test_same_image_yields_identical_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Determinism (§17 §16.7): carve twice → identical byte set (blob-deduped)."""
    image = tmp_path / "exhibit.dd"
    pad = (512 - (512 + len(_jpeg())) % 512) % 512
    image.write_bytes(b"\x00" * 512 + _jpeg() + b"\x00" * pad + _png())

    for cmd in (["init"], ["image", "add", "default", str(image)],
                ["hash", "default", "1"], ["carve", "default", "1"]):
        assert _run(list(cmd), tmp_path, monkeypatch) == 0

    conn = connect(str(tmp_path / "data" / "specter.db"))
    first = set(
        conn.execute("SELECT type, offset, length, content_sha256 FROM artifacts").fetchall()
    )
    conn.close()

    assert _run(["carve", "default", "1"], tmp_path, monkeypatch) == 0
    conn = connect(str(tmp_path / "data" / "specter.db"))
    second = set(
        conn.execute("SELECT type, offset, length, content_sha256 FROM artifacts").fetchall()
    )
    assert first == second
    assert len(first) == 2  # jpg + png, nothing else on the second pass
    conn.close()
