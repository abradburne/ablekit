from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .adg import SamplePaths, build_adg
from .folderinfo import sample_tags, write_folder_info
from .models import Pad

DEFAULT_USER_LIBRARY = Path.home() / 'Music' / 'Ableton' / 'User Library'


@dataclass
class KitReport:
    kit_name: str
    adg_path: Path
    sample_count: int
    dropped: int = 0
    loops: int = 0


def install_kit(expansion_name: str, kit_name: str, pads: list[Pad],
                user_library: Path = DEFAULT_USER_LIBRARY,
                dry_run: bool = False, dropped: int = 0) -> KitReport:
    """Copy a kit's samples into the User Library and write its .adg."""
    samples_dir = user_library / 'Samples' / 'Imported' / 'Ablekit' / expansion_name / kit_name
    adg_path = (user_library / 'Presets' / 'Instruments' / 'Drum Rack'
                / 'Ablekit' / expansion_name / f'{kit_name}.adg')

    sample_paths: SamplePaths = {}
    used_names: set[str] = set()
    copies: list[tuple[Path, Path]] = []
    for pad in pads:
        name = pad.sample.path.name
        if name in used_names:
            stem, ext = Path(name).stem, Path(name).suffix
            n = 2
            while f'{stem} {n}{ext}' in used_names:
                n += 1
            name = f'{stem} {n}{ext}'
        used_names.add(name)
        dest = samples_dir / name
        sample_paths[pad.note] = (str(dest), str(dest.relative_to(user_library)))
        copies.append((pad.sample.path, dest))

    if not dry_run:
        samples_dir.mkdir(parents=True, exist_ok=True)
        for src, dest in copies:
            shutil.copy2(src, dest)
        build_adg(pads, adg_path, sample_paths)
        # Write Live 12 browser tag sidecar so samples appear tagged in the browser
        sidecar_items = {
            dest.name: sample_tags(pad.sample.role)
            for pad, (_src, dest) in zip(pads, copies)
        }
        write_folder_info(samples_dir, sidecar_items)

    return KitReport(kit_name=kit_name, adg_path=adg_path,
                     sample_count=len(pads), dropped=dropped)
