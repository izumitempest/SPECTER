"""Configuration: load settings from the environment and ``.env``.

Spec: §12 (secrets come from the environment; production fails fast on
placeholder values), §13 (deployment). Keys are prefixed ``SPECTER_`` and
documented in ``.env.example``.

Tasks: M0-4.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime settings (M0-4). Values are resolved from the environment."""

    env: str = "development"
    data_dir: str = "./specter_data"
    db_path: str = ""
    token_ttl_hours: int = 8
    jwt_secret: str = ""
    chunk_size: int = 4 * 1024 * 1024          # 4 MiB (§7.1)
    scan_window: int = 128 * 1024 * 1024        # 128 MiB (§9.1)
    safety_cap: int = 50 * 1024 * 1024          # 50 MiB (§9.3)
    alignment: int = 512                        # sector alignment (§9.1)


def load_settings() -> Settings:
    """Load settings from the environment (M0-4).

    Production mode fails fast on placeholder values (§12). Not yet
    implemented — landing with ``specter.config`` (task M0-4).
    """
    raise NotImplementedError("M0-4: load_settings")