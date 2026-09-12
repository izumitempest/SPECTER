"""Job manager — job table, per-image lock, disk pre-flight (§4, §4.1).

- Jobs are persisted; statuses: queued → running → done / failed /
  paused_disk.
- **Per-image lock** (§4.1.1): at most one active carve/hash job per image;
  concurrent submissions queue (default) or reject with an audited error.
- **Disk pre-flight** (§4.1.3): free space checked before the job (≥ a
  configurable multiple of the image size) and re-checked every N artifacts.
  Exhaustion stops cleanly, marks the job ``paused_disk``, and audits it.
- **Idempotent re-run** (§4): carving is deterministic, so a failed job can
  be re-run to reproduce identical artifacts.

Tasks: M0-11, M2-6.
"""

from __future__ import annotations