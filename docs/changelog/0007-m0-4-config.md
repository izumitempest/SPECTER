# 0007 — M0-4 done: config loader (env + .env, production fail-fast)

- **Date:** 2026-09-15
- **Type:** change
- **Spec refs:** §12 (secrets from environment, fail-fast on placeholders),
  P-12 (JWT secret bootstrapped at `specter init`, keyfile or env)
- **Tag:** —

## Summary

Implemented `specter/config.py` — the first real module of M0. `load_settings`
resolves every `SPECTER_*` key by simple precedence — **process environment
wins, then `.env`, then the built-in default** — and validates eagerly:
integers must parse, `SPECTER_ENV` must be `development` or `production`, the
token TTL must be positive. In production mode the JWT secret must resolve
(from `SPECTER_JWT_SECRET` or the keyfile that `specter init` will write, per
P-12); placeholder or missing values fail fast with a clear message, as §12
requires.

## What changed

- `src/specter/config.py` — stub replaced with the real loader: `Settings`
  (frozen dataclass), `ConfigError`, `load_settings`, `resolve_jwt_secret`,
  and the placeholder blocklist. Docstring now states the resolution order
  instead of the stub notice.
- `tests/unit/test_config.py` — 10 unit tests: defaults, `.env` parsing,
  environment-over-file precedence, malformed integers/lines/env values, and
  the four production-mode secret cases (missing, placeholder, keyfile,
  env-supplied).
- `docs/TASKS.md` — M0-4 marked done.
- `docs/changelog/` — this entry and its index row.

## Verification

Logic reviewed against §12 and P-12 (keyfile name, placeholder fail-fast,
8 h default TTL). Tests require pytest; local venv creation is broken in this
session's environment, so CI runs them (Linux + Windows, 3.11/3.12).

## Next steps

- M0-5: `db.py` — schema v1, WAL + busy_timeout pragmas, `schema_version`.