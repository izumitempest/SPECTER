"""Authentication — JWT cookie, argon2id, CSRF, rate limiting (§12, P-12).

- Password hashing uses argon2id with pinned parameters
  (``memory_cost=65536 KiB, time_cost=3, parallelism=1``).
- The JWT secret is a random 256-bit value generated at ``specter init`` and
  stored in a 0600 keyfile (or supplied via environment); production fails
  fast if neither is present.
- Tokens are served in an httponly cookie with ``SameSite=Lax`` and a
  double-submit CSRF token on every form. Bearer tokens / localStorage are
  rejected (they trade CSRF for XSS token theft).

Tasks: M4-2.
"""

from __future__ import annotations