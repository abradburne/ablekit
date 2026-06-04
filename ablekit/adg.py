from __future__ import annotations

import gzip
from pathlib import Path
from xml.sax.saxutils import escape

from .models import Pad

TEMPLATES = Path(__file__).parent / 'templates'

# note -> (absolute sample path, User Library-relative sample path)
SamplePaths = dict[int, tuple[str, str]]


def _attr(value: str) -> str:
    """Escape a string for use inside a double-quoted XML attribute."""
    return escape(value, {'"': '&quot;'})


def _load(name: str) -> str:
    return (TEMPLATES / name).read_text()


def render_kit_xml(pads: list[Pad], preset_path: Path, sample_paths: SamplePaths) -> str:
    head = (_load('head.xml')
            .replace('@PRESET_PATH@', _attr(str(preset_path)))
            .replace('@PRESET_PATH_REL@', _attr('/'.join(preset_path.parts[-4:]))))
    pad_tpl = _load('pad.xml')
    parts = [head]
    for i, pad in enumerate(pads):
        abs_path, rel_path = sample_paths[pad.note]
        parts.append(pad_tpl
                     .replace('@BRANCH_ID@', str(i))
                     .replace('@PAD_NAME@', _attr(pad.sample.pad_name))
                     .replace('@SAMPLE_NAME@', _attr(pad.sample.pad_name))
                     .replace('@SAMPLE_PATH@', _attr(abs_path))
                     .replace('@SAMPLE_PATH_REL@', _attr(rel_path))
                     # Ableton stores drum pad notes inverted: 128 - midi note
                     .replace('@RECEIVING_NOTE@', str(128 - pad.note))
                     .replace('@CHOKE_GROUP@', str(pad.choke)))
    parts.append(_load('tail.xml'))
    return '\n'.join(parts)


def build_adg(pads: list[Pad], dest: Path, sample_paths: SamplePaths) -> None:
    xml = render_kit_xml(pads, dest, sample_paths)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(gzip.compress(xml.encode('utf-8')))
