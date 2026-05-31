"""Per-prefix Reservation file I/O.

Per ADR/0004: `<workspace>/Reservations/<prefix>.yaml` records claimed Numbers
keyed by Number string; duplicate Numbers collide at YAML parse time via the
Profile's duplicate-key rejection.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..validation.profile import dump_yaml, load_yaml
from .atomic import atomic_write_text


def reservations_dir(workspace: Path) -> Path:
    return workspace / "Reservations"


def reservation_path(workspace: Path, prefix: str) -> Path:
    return reservations_dir(workspace) / f"{prefix}.yaml"


def load_reservation(workspace: Path, prefix: str) -> dict[str, Any]:
    return load_yaml(reservation_path(workspace, prefix))


def write_reservation(workspace: Path, prefix: str, reservation: dict[str, Any]) -> str:
    text = dump_yaml(reservation)
    atomic_write_text(reservation_path(workspace, prefix), text)
    return text


def list_reservation_prefixes(workspace: Path) -> list[str]:
    rdir = reservations_dir(workspace)
    if not rdir.exists():
        return []
    return sorted(p.stem for p in rdir.glob("*.yaml"))
