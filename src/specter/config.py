"""Configuration: settings loaded from the environment and ``.env``.

Spec: §12 (secrets come from the environment; production fails fast on
placeholder values) and P-12 (the JWT secret is generated at bootstrap by
``specter init`` into a keyfile, or supplied via the environment).

All keys are prefixed ``SPECTER_`` and documented in ``.env.example``.

Resolution order for every key: the process environment wins, then the
``.env`` file, then the built-in default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

__all__ = [
    "KEYFILE_NAME",
    "ConfigError",
    "Settings",
    "load_settings",
    "resolve_jwt_secret",
]

#: Name of the JWT keyfile that ``specter init`` writes into the data dir.
KEYFILE_NAME = "specter.jwt.key"

_PRODUCTION = "production"
_DEVELOPMENT = "development"

#: Values that never count as a real secret (§12: fail fast on placeholders).
_PLACEHOLDERS: frozenset[str] = frozenset(
    {"", "change-me", "changeme", "placeholder", "todo", "default"}
)


class ConfigError(RuntimeError):
    """Configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    """Runtime settings resolved from the environment (§12, §13)."""

    env: str
    data_dir: Path
    db_path: Path
    token_ttl_hours: int
    jwt_secret: str | None
    chunk_size: int
    scan_window: int
    safety_cap: int
    alignment: int


def _read_env_file(path: Path) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines, ignoring blanks/comments/non-SPECTER keys."""
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return values
    for lineno, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigError(f"{path}:{lineno}: expected KEY=VALUE, got {raw!r}")
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("SPECTER_"):
            values[key] = value.strip()
    return values


def load_settings(
    *,
    environ: Mapping[str, str] | None = None,
    env_file: str | Path | None = None,
) -> Settings:
    """Resolve all settings.

    Parameters let tests supply a fake environment and ``.env`` path;
    defaults read the real process environment and ``./.env``.
    In production mode the JWT secret (env or keyfile) must resolve, or
    loading fails fast (§12).
    """
    source = os.environ if environ is None else environ
    file_values = _read_env_file(Path(".env") if env_file is None else Path(env_file))

    def get(key: str, default: str) -> str:
        if key in source:
            return source[key]
        return file_values.get(key, default)

    def get_int(key: str, default: int) -> int:
        raw = get(key, str(default))
        try:
            return int(raw)
        except ValueError:
            raise ConfigError(f"{key} must be an integer, got {raw!r}") from None

    env = get("SPECTER_ENV", _DEVELOPMENT)
    if env not in (_DEVELOPMENT, _PRODUCTION):
        raise ConfigError(
            f"SPECTER_ENV must be {_DEVELOPMENT!r} or {_PRODUCTION!r}, got {env!r}"
        )

    data_dir = Path(get("SPECTER_DATA_DIR", "./specter_data"))
    db_path = Path(get("SPECTER_DB_PATH", str(data_dir / "specter.db")))

    token_ttl_hours = get_int("SPECTER_TOKEN_TTL_HOURS", 8)
    if token_ttl_hours <= 0:
        raise ConfigError("SPECTER_TOKEN_TTL_HOURS must be a positive integer")

    raw_secret = get("SPECTER_JWT_SECRET", "")
    jwt_secret = raw_secret if raw_secret.lower() not in _PLACEHOLDERS else None

    settings = Settings(
        env=env,
        data_dir=data_dir,
        db_path=db_path,
        token_ttl_hours=token_ttl_hours,
        jwt_secret=jwt_secret,
        chunk_size=get_int("SPECTER_CHUNK_SIZE", 4 * 1024 * 1024),
        scan_window=get_int("SPECTER_SCAN_WINDOW", 128 * 1024 * 1024),
        safety_cap=get_int("SPECTER_SAFETY_CAP", 50 * 1024 * 1024),
        alignment=get_int("SPECTER_ALIGNMENT", 512),
    )
    if env == _PRODUCTION:
        resolve_jwt_secret(settings)
    return settings


def resolve_jwt_secret(settings: Settings) -> str:
    """Return the JWT secret from the environment or the keyfile (P-12).

    Raises ConfigError when neither exists or the value is a placeholder.
    """
    if settings.jwt_secret is not None:
        return settings.jwt_secret
    keyfile = settings.data_dir / KEYFILE_NAME
    try:
        secret = keyfile.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise ConfigError(
            "No JWT secret: set SPECTER_JWT_SECRET or run `specter init` "
            f"to create {keyfile}"
        ) from exc
    if secret.lower() in _PLACEHOLDERS:
        raise ConfigError(f"JWT secret in {keyfile} is empty or a placeholder")
    return secret