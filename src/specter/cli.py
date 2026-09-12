"""Command-line interface: ``specter ...``.

The M0 vertical slice (spec §18 M0 exit criteria): init → image add → hash
→ carve → list. Each command is implemented under the CLI milestone
(tasks M0-12, and refined as engines land).

Every command that touches a case writes audit entries (§8), including the
failure path.
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="specter",
    help="SPECTER — offline forensic triage platform (educational).",
    no_args_is_help=True,
)


@app.command("init")
def init(
    data_dir: str = typer.Option("./specter_data", help="Data directory (cases, blobs, database)."),
) -> None:
    """Bootstrap a deployment: create the data directory, database schema,
    and JWT keyfile (§12, P-12). Task M0-12."""
    raise NotImplementedError("M0-12: specter init")


@app.command("image")
def image_add(
    case: str = typer.Argument(..., help="Case name or ID"),
    path: str = typer.Argument(..., help="Path to the image file (.dd/.img)"),
    copy: bool = typer.Option(False, "--copy", help="Verify-copy instead of register-by-path (§6)"),
) -> None:
    """Register an image in a case (§6). Task M0-12."""
    raise NotImplementedError("M0-12: specter image add")


@app.command("hash")
def hash_image(
    case: str = typer.Argument(..., help="Case name or ID"),
    image: str = typer.Argument(..., help="Image name or ID"),
) -> None:
    """Acquisition hashing: whole-image SHA-256 + chunk sidecar (§7.1). Task M0-12."""
    raise NotImplementedError("M0-12: specter hash")


@app.command("carve")
def carve(
    case: str = typer.Argument(..., help="Case name or ID"),
    image: str = typer.Argument(..., help="Image name or ID"),
) -> None:
    """Run the carving pass over a hashed image (§9). Task M0-12."""
    raise NotImplementedError("M0-12: specter carve")


@app.command("list")
def ls(
    what: str = typer.Argument(..., help="What to list: cases | images | artifacts"),
    case: str = typer.Option("", help="Restrict to a case (for artifacts)"),
) -> None:
    """List cases, images, or recovered artifacts. Task M0-12."""
    raise NotImplementedError("M0-12: specter list")