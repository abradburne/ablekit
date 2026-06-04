from __future__ import annotations

from pathlib import Path

from .models import Expansion

SHARED = Path('/Users/Shared')


def scan_expansion(path: Path) -> Expansion | None:
    """Return an Expansion if path looks like a Maschine expansion, else None."""
    groups = path / 'Groups'
    samples = path / 'Samples'
    if not (groups.is_dir() and samples.is_dir()):
        return None
    kit_names = sorted(p.stem for p in groups.rglob('*.mxgrp'))
    if not kit_names:
        return None
    return Expansion(name=path.name, path=path, kit_names=kit_names)


def discover(root: Path = SHARED) -> list[Expansion]:
    """Scan root's children for Maschine expansions."""
    found: list[Expansion] = []
    try:
        children = sorted(root.iterdir())
    except (PermissionError, FileNotFoundError):
        return found
    for child in children:
        if not child.is_dir():
            continue
        exp = scan_expansion(child)
        if exp:
            found.append(exp)
    return found
