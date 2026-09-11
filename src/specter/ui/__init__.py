"""UI layer — server-rendered Jinja2 templates + htmx (§11).

The UI is deliberately server-rendered to keep the codebase Python-readable
end-to-end. JavaScript is limited to ~300 lines and only powers hex-viewer
navigation.

Safety rule (§11): recovered files are served as
``application/octet-stream`` and shown only as hex/text — they are
attacker-controlled bytes and must never be rendered as their native type in
a browser.

Layout:

- ``templates/`` — dashboard, case, triage, hex viewer, audit trail
- ``static/``   — the small JavaScript/CSS bundle

Tasks: M4-5.
"""

from __future__ import annotations