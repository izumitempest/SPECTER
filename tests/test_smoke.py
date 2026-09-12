"""Smoke tests — the M0 baseline assures the package, spec state, and CLI boot.

M0 exit criteria (spec §18): repository, CI, and a CLI vertical slice.
"""

from __future__ import annotations

import subprocess
import sys


def test_package_importable_and_versioned() -> None:
    import specter

    assert specter.__version__ == "0.1.0"
    assert specter.__spec_version__ == "3.3"


def test_cli_help_exits_zero() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "specter", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "specter" in result.stdout.lower()