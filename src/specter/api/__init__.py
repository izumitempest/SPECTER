"""API layer — FastAPI app, authentication, case-scoped authorization (§12).

Single-process deployment is normative (E-07): the reference runs one API
process. Multi-worker Uvicorn/Gunicorn is out of scope — it would fork the
in-process job pool, multiply audit writers, and partition the rate limiter.

Layout:

- ``app``  — application factory
- ``auth`` — JWT cookie auth, argon2id, CSRF, rate limiting
- ``deps`` — ``require_case_access`` (case-scoped authorization)
"""

from __future__ import annotations