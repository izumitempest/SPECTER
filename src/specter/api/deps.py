"""FastAPI dependencies — case-scoped authorization (§12, P-12).

``require_case_access`` resolves the resource's case and requires
`CaseMember` membership **or admin** *before* any file handle is opened, so
the check is structurally impossible to omit from a new route — write it as a
dependency, never as optional boilerplate.

Two normative rules:

- Cross-case access returns **404, not 403** — no existence oracle.
- Admin bypass is **visible, never silent**: the actor's role is recorded in
  every audit entry, so an admin crossing case boundaries shows up in the
  trail.

Tasks: M4-3.
"""

from __future__ import annotations