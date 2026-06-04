from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .folderinfo import KIT_TAGS, write_folder_info
from .installer import DEFAULT_USER_LIBRARY, KitReport, install_kit
from .layout import assign_pads
from .loops import install_loops
from .matcher import match_expansion
from .models import Expansion, Role


@dataclass
class ConversionResult:
    expansion: str
    kits: list[KitReport] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # kits with zero matched samples
    unmatched: int = 0                                # classifiable audio claimed by no kit
    ignored: int = 0                                  # audio ignored by design (Instruments/ etc.)


def convert_expansion(exp: Expansion,
                      user_library: Path = DEFAULT_USER_LIBRARY,
                      dry_run: bool = False,
                      only_kits: set[str] | None = None,
                      progress: Callable[[str], None] | None = None) -> ConversionResult:
    kits, unmatched, ignored = match_expansion(exp)
    result = ConversionResult(expansion=exp.name,
                              unmatched=len(unmatched),
                              ignored=len(ignored))
    for kit in kits:
        if only_kits is not None and kit.name not in only_kits:
            continue
        if not kit.samples:
            result.skipped.append(kit.name)
            continue
        # Split loops out before assigning pads — loops go to their own folder,
        # not onto drum rack pads.
        loop_samples = [s for s in kit.samples if s.role is Role.LOOP]
        rack_samples = [s for s in kit.samples if s.role is not Role.LOOP]
        pads, dropped = assign_pads(rack_samples)
        report = install_kit(exp.name, kit.name, pads, user_library,
                             dry_run=dry_run, dropped=len(dropped))
        loop_count = install_loops(exp.name, kit.name, loop_samples,
                                   user_library, dry_run=dry_run)
        report.loops = loop_count
        result.kits.append(report)
        if progress:
            progress(kit.name)

    if not dry_run and result.kits:
        # Tag all .adg files in the kit folder — glob-based so we don't lose entries
        # from kits converted in a prior selective run (sidecar would otherwise overwrite
        # only the kits from THIS run and orphan earlier entries).
        adg_dir = result.kits[0].adg_path.parent
        items = {p.name: KIT_TAGS for p in sorted(adg_dir.glob('*.adg'))}
        write_folder_info(adg_dir, items)

    return result
