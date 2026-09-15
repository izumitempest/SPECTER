"""Unit tests for ``specter.config`` (M0-4; spec §12, P-12)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specter.config import KEYFILE_NAME, ConfigError, load_settings, resolve_jwt_secret

MISSING_ENV_FILE = Path("does-not-exist.env")


def test_defaults_in_development(tmp_path: Path) -> None:
    settings = load_settings(environ={}, env_file=tmp_path / MISSING_ENV_FILE)
    assert settings.env == "development"
    assert settings.chunk_size == 4 * 1024 * 1024
    assert settings.scan_window == 128 * 1024 * 1024
    assert settings.safety_cap == 50 * 1024 * 1024
    assert settings.alignment == 512
    assert settings.jwt_secret is None


def test_env_file_is_read_when_environment_is_silent(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("SPECTER_CHUNK_SIZE=1024\n", encoding="utf-8")
    settings = load_settings(environ={}, env_file=env_file)
    assert settings.chunk_size == 1024


def test_environment_overrides_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("SPECTER_CHUNK_SIZE=1024\n", encoding="utf-8")
    settings = load_settings(environ={"SPECTER_CHUNK_SIZE": "2048"}, env_file=env_file)
    assert settings.chunk_size == 2048


def test_invalid_integer_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_settings(
            environ={"SPECTER_CHUNK_SIZE": "not-a-number"},
            env_file=tmp_path / MISSING_ENV_FILE,
        )


def test_invalid_env_value_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_settings(
            environ={"SPECTER_ENV": "staging"}, env_file=tmp_path / MISSING_ENV_FILE
        )


def test_malformed_env_file_line_is_rejected(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("SPECTER_CHUNK_SIZE line without equals\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_settings(environ={}, env_file=env_file)


def test_production_requires_a_jwt_secret(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_settings(
            environ={"SPECTER_ENV": "production", "SPECTER_DATA_DIR": str(tmp_path)},
            env_file=tmp_path / MISSING_ENV_FILE,
        )


def test_production_rejects_placeholder_secret(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_settings(
            environ={"SPECTER_ENV": "production", "SPECTER_JWT_SECRET": "change-me"},
            env_file=tmp_path / MISSING_ENV_FILE,
        )


def test_production_accepts_keyfile(tmp_path: Path) -> None:
    (tmp_path / KEYFILE_NAME).write_text("s3cret\n", encoding="utf-8")
    settings = load_settings(
        environ={"SPECTER_ENV": "production", "SPECTER_DATA_DIR": str(tmp_path)},
        env_file=tmp_path / MISSING_ENV_FILE,
    )
    assert resolve_jwt_secret(settings) == "s3cret"


def test_production_accepts_env_secret() -> None:
    settings = load_settings(
        environ={"SPECTER_ENV": "production", "SPECTER_JWT_SECRET": "s3cret"},
        env_file=MISSING_ENV_FILE,
    )
    assert settings.jwt_secret == "s3cret"