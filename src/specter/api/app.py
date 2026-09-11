"""FastAPI application factory (§4, §12, E-07).

Builds the app with configuration, middleware (CSP), and routers. The UI is
server-rendered Jinja2 (``specter.ui``); this module serves JSON endpoints.

Deployment constraint (E-07): run under a single API process — uvicorn with
one worker; do not enable multi-worker mode for v1.

Tasks: M4-1.
"""

from __future__ import annotations


def create_app() -> object:
    """Build the FastAPI application (M4-1). Not yet implemented."""
    raise NotImplementedError("M4-1: create_app")