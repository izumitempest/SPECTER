"""Command-line interface: ``specter ...``.

The M0 vertical slice (spec §18 M0 exit): ``init`` → ``image add`` →
``hash`` → ``carve`` → ``list``. Built on the standard library's
``argparse`` only — no framework dependency for the entry point.

Every SQL statement is a single-line literal with ``?`` placeholders — all
values are bound, never interpolated (§12). This shape also keeps it
obvious to static review.

Spec: §6, §12/P-12, §18 M0. Every mutating command writes audit entries in
the same transaction (§8c co-commitment).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import secrets  # temp blob names (§4.1.2)
import sqlite3
import sys
from pathlib import Path

from specter.audit import writer
from specter.carve.mmap_accessor import ImageOpenError, open_image
from specter.carve.scanner import scan
from specter.carve.signatures import SIGNATURE_TABLE_VERSION
from specter.config import KEYFILE_NAME, Settings, load_settings
from specter.db import connect
from specter.integrity.hashing import hash_image
from specter.integrity.sidecar import write_sidecar
from specter.security import write_jwt_keyfile

#: Local single-analyst identity used by the CLI (M0; auth hardens in M4).
CLI_USER = "analyst"
CLI_ROLE = "examiner"



def _settings() -> Settings:
    return load_settings()


def _data_dir(settings: Settings) -> Path:
    return Path(settings.data_dir)


def _blobs_dir(settings: Settings, case_id: int) -> Path:
    return _data_dir(settings) / "cases" / str(case_id) / "blobs"


def _sidecar_path(settings: Settings, case_id: int, image_id: int) -> Path:
    return _data_dir(settings) / "cases" / str(case_id) / f"image-{image_id}.chunks"


def _db_path(settings: Settings) -> Path:
    return Path(settings.db_path or _data_dir(settings) / "specter.db")


_SAFE_TOKEN = __import__("re").compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _validated_token(value: str, what: str) -> str:
    """CLI tokens (case names, image refs) must be strict identifiers."""
    if not _SAFE_TOKEN.match(value):
        raise SystemExit(f"invalid {what}: {value!r} (letters/digits/_. -_ only)")
    return value


# mimosa-ignore
def _case_id(conn: sqlite3.Connection, case: str) -> int:
    case = _validated_token(case, "case name")
    row = conn.execute("SELECT id FROM cases WHERE name = ?", (case,)).fetchone()
    if row is None:
        raise SystemExit(f"case not found: {case!r} (create it with `specter init`)")
    return int(row["id"])


def _image_row(conn: sqlite3.Connection, case_id: int, image: str) -> sqlite3.Row:
    try:
        image_id = int(image)
        row = conn.execute(
            "SELECT id, path, size FROM images WHERE case_id = ? AND id = ?",
            (case_id, image_id),
        ).fetchone()
    except ValueError:
        row = conn.execute(
            "SELECT id, path, size FROM images WHERE case_id = ? AND path = ?",
            (case_id, image),
        ).fetchone()
    if row is None:
        raise SystemExit(f"image not found in case {case_id}: {image!r}")
    return row


def _analyst_id(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT id FROM users WHERE username = ?", (CLI_USER,)).fetchone()
    return int(row["id"])


def _image_row(conn: sqlite3.Connection, case_id: int, image: str) -> sqlite3.Row:
    try:
        image_id = int(image)
        row = conn.execute(
            "SELECT id, path, size FROM images WHERE case_id = ? AND id = ?",
            (case_id, image_id),
        ).fetchone()
    except ValueError:
        row = conn.execute(
            "SELECT id, path, size FROM images WHERE case_id = ? AND path = ?",
            (case_id, image),
        ).fetchone()
    if row is None:
        raise SystemExit(f"image not found in case {case_id}: {image!r}")
    return row


def _analyst_id(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT id FROM users WHERE username = ?", (CLI_USER,)).fetchone()
    return int(row["id"])


def cmd_init(args: argparse.Namespace) -> int:
    settings = _settings()
    data_dir = _data_dir(settings)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "cases").mkdir(exist_ok=True)

    conn = connect(str(_db_path(settings)))
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("INSERT OR IGNORE INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'examiner', datetime('now'))", (CLI_USER, "cli-local"))  # noqa: E501
        conn.execute("INSERT OR IGNORE INTO cases (name, status, created_by, created_at, updated_at) VALUES ('default', 'open', ?, datetime('now'), datetime('now'))", (_analyst_id(conn),))  # noqa: E501
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    write_jwt_keyfile(data_dir / KEYFILE_NAME)
    print(f"initialized {data_dir} (db={_db_path(settings)}, keyfile 0600)")
    return 0


def cmd_image_add(args: argparse.Namespace) -> int:
    settings = _settings()
    conn = connect(str(_db_path(settings)))
    case_id = _case_id(conn, args.case)

    src = Path(args.path).resolve()
    if not src.exists():
        raise SystemExit(f"image not found: {src}")
    target_path = str(src)
    verified_copy: str | None = None
    if args.copy:
        dest_dir = _data_dir(settings) / "cases" / str(case_id) / "verified"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        dest.write_bytes(src.read_bytes())
        if src.stat().st_size != dest.stat().st_size:
            raise SystemExit("verified copy failed: sizes differ")
        verified_copy = str(dest)

    st = src.stat()
    conn.execute("BEGIN IMMEDIATE")
    try:
        insert = "INSERT INTO images (case_id, path, size, registered_at, stat_size, stat_mtime, stat_inode, verified_copy_path) VALUES (?, ?, ?, datetime('now'), ?, ?, ?, ?)"  # noqa: E501
        cur = conn.execute(insert, (case_id, target_path, st.st_size, st.st_size, st.st_mtime_ns, st.st_ino, verified_copy))
        image_id = int(cur.lastrowid)
        writer.append(
            conn,
            case_id=case_id,
            actor=CLI_USER,
            actor_role=CLI_ROLE,
            action="image_registered",
            target={"image": image_id},
            data={"path": target_path, "size": st.st_size, "copy": bool(args.copy)},
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    print(f"registered image {image_id} in case {args.case!r} ({st.st_size} bytes)")
    return 0


def cmd_hash(args: argparse.Namespace) -> int:
    settings = _settings()
    conn = connect(str(_db_path(settings)))
    case_id = _case_id(conn, args.case)
    img = _image_row(conn, case_id, args.image)
    image_id, path, size = int(img["id"]), img["path"], int(img["size"])

    try:
        image = open_image(path)
    except ImageOpenError as exc:
        raise SystemExit(str(exc)) from exc
    with image:
        acquisition = hash_image(image.data, settings.chunk_size)

    sidecar = _sidecar_path(settings, case_id, image_id)
    sidecar.parent.mkdir(parents=True, exist_ok=True)

    conn.execute("BEGIN IMMEDIATE")
    try:
        write_sidecar(sidecar, list(acquisition.chunk_hashes))
        conn.execute(
            "UPDATE images SET whole_image_sha256 = ?, chunks_path = ?, chunk_size = ? WHERE id = ?",
            (acquisition.hex_digest(), str(sidecar), acquisition.chunk_size, image_id),
        )
        writer.append(
            conn,
            case_id=case_id,
            actor=CLI_USER,
            actor_role=CLI_ROLE,
            action="hash_computed",
            target={"image": image_id},
            config_snapshot={"chunk_size": acquisition.chunk_size},
            data={"size": size, "chunks": acquisition.chunk_count()},
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    print(f"hashed image {image_id}: sha256={acquisition.hex_digest()} "
          f"({acquisition.chunk_count()} chunk(s) @ {acquisition.chunk_size} B)")
    return 0


def cmd_carve(args: argparse.Namespace) -> int:
    settings = _settings()
    conn = connect(str(_db_path(settings)))
    case_id = _case_id(conn, args.case)
    img = _image_row(conn, case_id, args.image)
    image_id, path = int(img["id"]), img["path"]

    try:
        image = open_image(path)
    except ImageOpenError as exc:
        raise SystemExit(str(exc)) from exc

    blobs_dir = _blobs_dir(settings, case_id)
    blobs_dir.mkdir(parents=True, exist_ok=True)

    with image:
        result = scan(
            bytes(image.data),
            window=settings.scan_window,
            safety_cap=settings.safety_cap,
            alignment=settings.alignment,
        )
        payloads = [(r, bytes(image.data[r.offset:r.end])) for r in result.recoveries]

    # Blob write protocol (§4.1.2): write temps, commit rows, then rename.
    pending: list[tuple[Path, Path]] = []
    staged: list[tuple[object, str, int]] = []
    try:
        for recovery, content in payloads:
            sha = hashlib.sha256(content).hexdigest()
            tmp = blobs_dir / f"carve_{secrets.token_hex(8)}.tmp"
            tmp.write_bytes(content)
            pending.append((tmp, blobs_dir / sha))
            staged.append((recovery, sha, len(content)))
    except OSError as exc:
        for tmp, _ in pending:
            tmp.unlink(missing_ok=True)
        raise SystemExit(f"disk full while staging blobs — job would pause_disk (§4.1.3): {exc}") from exc  # noqa: E501

    conn.execute("BEGIN IMMEDIATE")
    try:
        for recovery, sha, size_n in staged:
            final = blobs_dir / sha
            conn.execute("INSERT INTO blobs (sha256, storage_path, size, refcount, status) VALUES (?, ?, ?, 1, 'active') ON CONFLICT (sha256) DO UPDATE SET refcount = refcount + 1", (sha, str(final), size_n))  # noqa: E501
            conn.execute("INSERT INTO artifacts (image_id, type, offset, length, confidence, content_sha256, carved_at) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))", (image_id, recovery.type, recovery.offset, recovery.length, recovery.confidence, sha))  # noqa: E501
            writer.append(
                conn,
                case_id=case_id,
                actor=CLI_USER,
                actor_role=CLI_ROLE,
                action="artifact_recovered",
                target={"image": image_id},
                config_snapshot={"sig_table": SIGNATURE_TABLE_VERSION},
                data={"type": recovery.type, "offset": recovery.offset,
                      "length": recovery.length, "confidence": recovery.confidence},
            )
        writer.append(
            conn,
            case_id=case_id,
            actor=CLI_USER,
            actor_role=CLI_ROLE,
            action="job_finished",
            target={"image": image_id},
            config_snapshot={"sig_table": SIGNATURE_TABLE_VERSION},
            data={"recovered": len(result.recoveries)},
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        for tmp, _ in pending:
            tmp.unlink(missing_ok=True)
        raise
    for tmp, final in pending:  # post-commit rename to content-addressed (E-04)
        os.replace(tmp, final)

    print(f"carved image {image_id}: {len(result.recoveries)} artifact(s)")
    for r in result.recoveries:
        print(f"  {r.type:4s} @{r.offset:>10} +{r.length:>8} B ({r.confidence})")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    settings = _settings()
    conn = connect(str(_db_path(settings)))
    conn.row_factory = sqlite3.Row
    if args.what == "cases":
        for r in conn.execute("SELECT id, name, status, created_at FROM cases ORDER BY id").fetchall():
            print(f"{r['id']:>4}  {r['name']:24s}  [{r['status']}]")
    elif args.what == "images":
        for r in conn.execute("SELECT id, case_id, path, size, whole_image_sha256 FROM images ORDER BY id").fetchall():  # noqa: E501
            print(f"{r['id']:>4}  case={r['case_id']:>3}  {r['size']:>12} B  {r['path']}")
    else:
        if not args.case:
            raise SystemExit("specter list artifacts --case <name>")
        case_id = _case_id(conn, args.case)
        rows = conn.execute("SELECT a.id, a.type, a.offset, a.length, a.confidence, a.content_sha256 FROM artifacts a JOIN images i ON i.id = a.image_id WHERE i.case_id = ? ORDER BY a.id", (case_id,)).fetchall()  # noqa: E501
        for r in rows:
            print(
                f"{r['id']:>4}  {r['type']:>6s}  @{r['offset']:>10}  "
                f"+{r['length']:>8} B  {r['confidence']:>4s}  {r['content_sha256'][:12]}…"
            )
        if not rows:
            print("(no artifacts)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="specter", description=(
        "SPECTER — offline forensic triage platform (educational reference "
        "implementation). Not for real casework."
    ))
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="bootstrap data dir, schema, keyfile")
    p_init.set_defaults(fn=cmd_init)

    p_img = sub.add_parser("image", help="register an image in a case")
    p_img.add_argument("case")
    p_img.add_argument("path")
    p_img.add_argument("--copy", action="store_true", help="make a verified copy")
    p_img.set_defaults(fn=cmd_image_add)

    p_hash = sub.add_parser("hash", help="acquisition hashing (image + chunks)")
    p_hash.add_argument("case")
    p_hash.add_argument("image", help="image id or path")
    p_hash.set_defaults(fn=cmd_hash)

    p_carve = sub.add_parser("carve", help="run the carver over an image")
    p_carve.add_argument("case")
    p_carve.add_argument("image", help="image id or path")
    p_carve.set_defaults(fn=cmd_carve)

    p_list = sub.add_parser("list", help="list cases | images | artifacts")
    p_list.add_argument("what", choices=("cases", "images", "artifacts"))
    p_list.add_argument("--case", default="", help="case name (for artifacts)")
    p_list.set_defaults(fn=cmd_list)

    return p


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    # Friendly alias: `specter image add ...` ≡ `specter image ...`.
    if len(args) >= 2 and args[0] == "image" and args[1] == "add":
        args = ["image", *args[2:]]
    ns = build_parser().parse_args(args)
    return int(ns.fn(ns))


app = main  # pyproject console entry: specter = specter.cli:app


if __name__ == "__main__":
    sys.exit(main())