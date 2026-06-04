"""Build ablekit ADG templates from a user-saved single-pad Drum Rack .adg.

Usage:
    uv run python scripts/build_templates.py "$HOME/Music/Ableton/User Library/Presets/Instruments/Drum Rack/Drum Rack.adg"

The script:
1. Gunzips and reads the .adg as raw text (preserving Live's exact formatting).
2. Splits into head / pad / tail.
3. Inserts @TOKEN@ markers consumed by ablekit/adg.py.
4. Asserts correctness (all tokens present, no leftover /Users/ paths, round-trip XML).
5. Writes ablekit/templates/{head,pad,tail}.xml.
"""
from __future__ import annotations

import gzip
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DEST = Path(__file__).resolve().parent.parent / 'ablekit' / 'templates'

# ---------------------------------------------------------------------------
# FilePresetRef blocks that replace the AbletonDefaultPresetRef blocks Live
# writes when saving a rack as a device (not a user preset).  These are what
# ablekit/adg.py needs in the output .adg so that Live resolves the preset
# back to the file on disk.  Indentation matches Live's serialization style.
#
# DrumGroupDevice > LastPresetRef  (4 tabs deep inside the Value wrapper)
# ---------------------------------------------------------------------------
_LAST_PRESET_REF_BLOCK = """\
\t\t\t\t\t<LastPresetRef>
\t\t\t\t\t\t<Value>
\t\t\t\t\t\t\t<FilePresetRef Id="0">
\t\t\t\t\t\t\t\t<FileRef>
\t\t\t\t\t\t\t\t\t<RelativePathType Value="6" />
\t\t\t\t\t\t\t\t\t<RelativePath Value="@PRESET_PATH_REL@" />
\t\t\t\t\t\t\t\t\t<Path Value="@PRESET_PATH@" />
\t\t\t\t\t\t\t\t\t<Type Value="2" />
\t\t\t\t\t\t\t\t\t<LivePackName Value="" />
\t\t\t\t\t\t\t\t\t<LivePackId Value="" />
\t\t\t\t\t\t\t\t\t<OriginalFileSize Value="0" />
\t\t\t\t\t\t\t\t\t<OriginalCrc Value="0" />
\t\t\t\t\t\t\t\t</FileRef>
\t\t\t\t\t\t\t</FilePresetRef>
\t\t\t\t\t\t</Value>
\t\t\t\t\t</LastPresetRef>"""

# GroupDevicePreset > PresetRef  (2 tabs deep)
_PRESET_REF_BLOCK = """\
\t\t<PresetRef>
\t\t\t<FilePresetRef Id="0">
\t\t\t\t<FileRef>
\t\t\t\t\t<RelativePathType Value="6" />
\t\t\t\t\t<RelativePath Value="@PRESET_PATH_REL@" />
\t\t\t\t\t<Path Value="@PRESET_PATH@" />
\t\t\t\t\t<Type Value="2" />
\t\t\t\t\t<LivePackName Value="" />
\t\t\t\t\t<LivePackId Value="" />
\t\t\t\t\t<OriginalFileSize Value="0" />
\t\t\t\t\t<OriginalCrc Value="0" />
\t\t\t\t</FileRef>
\t\t\t</FilePresetRef>
\t\t</PresetRef>"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_block_bounds(lines: list[str], open_tag_re: str, close_tag: str,
                       start: int = 0) -> tuple[int, int]:
    """Return (first_line_index, last_line_index) for a block delimited by an
    opening tag (regex) and a closing tag (literal), both inclusive."""
    open_re = re.compile(open_tag_re)
    for i in range(start, len(lines)):
        if open_re.search(lines[i]):
            for j in range(i, len(lines)):
                if close_tag in lines[j]:
                    return i, j
            raise ValueError(f'No closing {close_tag!r} after line {i}')
    raise ValueError(f'Opening tag {open_tag_re!r} not found after line {start}')


def _replace_block(lines: list[str], open_tag_re: str, close_tag: str,
                   replacement: str, start: int = 0) -> tuple[list[str], int]:
    """Replace a block in lines with replacement text; return new lines and the
    index of the line following the replacement."""
    i, j = _find_block_bounds(lines, open_tag_re, close_tag, start)
    new_lines = lines[:i] + replacement.splitlines() + lines[j + 1:]
    return new_lines, i + len(replacement.splitlines())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_templates(adg_path: Path) -> None:
    # 1. Gunzip and decode
    raw = gzip.decompress(adg_path.read_bytes()).decode('utf-8')
    lines = raw.splitlines()

    # ----- Locate split boundaries -----
    # head ends at (and includes) the line containing <BranchPresets>
    branch_presets_line = next(
        i for i, l in enumerate(lines) if '<BranchPresets>' in l
    )
    # pad is the first DrumBranchPreset block
    dbp_open = next(
        i for i, l in enumerate(lines) if re.search(r'<DrumBranchPreset\s+Id="', l)
    )
    dbp_close = next(
        i for i, l in enumerate(lines) if '</DrumBranchPreset>' in l
    )
    # tail starts at </BranchPresets>
    branch_presets_close = next(
        i for i, l in enumerate(lines) if '</BranchPresets>' in l
    )

    # ----- Extract raw sections -----
    head_lines = lines[:branch_presets_line + 1]
    pad_lines  = lines[dbp_open:dbp_close + 1]
    tail_lines = lines[branch_presets_close:]

    # ==================================================================
    # HEAD tokenisation
    # ==================================================================
    # There are two preset-ref locations in the head:
    #   (A) DrumGroupDevice > LastPresetRef  — Live 12.4 saves AbletonDefaultPresetRef
    #   (B) GroupDevicePreset > PresetRef    — likewise
    # Replace both wholesale with FilePresetRef + tokens.
    #
    # (A) DrumGroupDevice's LastPresetRef block
    head_lines, _ = _replace_block(
        head_lines,
        open_tag_re=r'<LastPresetRef>',
        close_tag='</LastPresetRef>',
        replacement=_LAST_PRESET_REF_BLOCK,
    )
    # (B) GroupDevicePreset's PresetRef block
    head_lines, _ = _replace_block(
        head_lines,
        open_tag_re=r'<PresetRef>',
        close_tag='</PresetRef>',
        replacement=_PRESET_REF_BLOCK,
    )

    # ==================================================================
    # PAD tokenisation
    # ==================================================================
    pad_text = '\n'.join(pad_lines)

    # DrumBranchPreset Id
    pad_text = re.sub(
        r'(<DrumBranchPreset\s+Id=")[^"]*(")',
        r'\g<1>@BRANCH_ID@\2',
        pad_text, count=1,
    )

    # First <Name Value="..."> in the branch (the pad label, line ~2)
    pad_text = re.sub(
        r'(<Name Value=")[^"]*(")',
        r'\g<1>@PAD_NAME@\2',
        pad_text, count=1,
    )

    # MultiSamplePart's <Name Value="..."> (the sample name label)
    # It appears after the MultiSamplePart opening tag
    msp_pos = pad_text.index('<MultiSamplePart ')
    first_part  = pad_text[:msp_pos]
    second_part = pad_text[msp_pos:]
    second_part = re.sub(
        r'(<Name Value=")[^"]*(")',
        r'\g<1>@SAMPLE_NAME@\2',
        second_part, count=1,
    )
    pad_text = first_part + second_part

    # In SampleRef > FileRef: RelativePath, Path, OriginalFileSize, OriginalCrc
    sample_ref_match = re.search(r'<SampleRef>', pad_text)
    if not sample_ref_match:
        raise ValueError('No <SampleRef> found in pad')
    sr_start = sample_ref_match.start()
    sr_end   = pad_text.index('</SampleRef>') + len('</SampleRef>')
    sample_ref_text = pad_text[sr_start:sr_end]

    sample_ref_text = re.sub(
        r'(<RelativePath Value=")[^"]*(")',
        r'\g<1>@SAMPLE_PATH_REL@\2',
        sample_ref_text, count=1,
    )
    sample_ref_text = re.sub(
        r'(<Path Value=")[^"]*(")',
        r'\g<1>@SAMPLE_PATH@\2',
        sample_ref_text, count=1,
    )
    sample_ref_text = re.sub(
        r'(<OriginalFileSize Value=")[^"]*(")',
        r'\g<1>0\2',
        sample_ref_text, count=1,
    )
    sample_ref_text = re.sub(
        r'(<OriginalCrc Value=")[^"]*(")',
        r'\g<1>0\2',
        sample_ref_text, count=1,
    )
    pad_text = pad_text[:sr_start] + sample_ref_text + pad_text[sr_end:]

    # ZoneSettings: ReceivingNote and ChokeGroup
    zone_match = re.search(r'<ZoneSettings>', pad_text)
    if not zone_match:
        raise ValueError('No <ZoneSettings> in pad')
    zs_start = zone_match.start()
    zs_end   = pad_text.index('</ZoneSettings>') + len('</ZoneSettings>')
    zone_text = pad_text[zs_start:zs_end]
    zone_text = re.sub(
        r'(<ReceivingNote Value=")[^"]*(")',
        r'\g<1>@RECEIVING_NOTE@\2',
        zone_text, count=1,
    )
    zone_text = re.sub(
        r'(<ChokeGroup Value=")[^"]*(")',
        r'\g<1>@CHOKE_GROUP@\2',
        zone_text, count=1,
    )
    pad_text = pad_text[:zs_start] + zone_text + pad_text[zs_end:]

    # ==================================================================
    # Assertions
    # ==================================================================
    head_text = '\n'.join(head_lines)
    tail_text = '\n'.join(tail_lines)

    expected_tokens = {
        '@PRESET_PATH@', '@PRESET_PATH_REL@',
        '@BRANCH_ID@', '@PAD_NAME@', '@SAMPLE_NAME@',
        '@SAMPLE_PATH@', '@SAMPLE_PATH_REL@',
        '@RECEIVING_NOTE@', '@CHOKE_GROUP@',
    }

    # Each token must appear in the correct section
    for tok in ('@PRESET_PATH@', '@PRESET_PATH_REL@'):
        count = head_text.count(tok)
        assert count == 2, (
            f'{tok} should appear 2× in head (LastPresetRef + PresetRef), got {count}'
        )
    for tok in ('@BRANCH_ID@', '@PAD_NAME@', '@SAMPLE_NAME@',
                '@SAMPLE_PATH@', '@SAMPLE_PATH_REL@',
                '@RECEIVING_NOTE@', '@CHOKE_GROUP@'):
        count = pad_text.count(tok)
        assert count == 1, f'{tok} should appear 1× in pad, got {count}'

    # No leftover absolute /Users/ paths
    assert '/Users/' not in head_text, 'head still contains /Users/ path'
    assert '/Users/' not in pad_text,  'pad still contains /Users/ path'

    # Round-trip: substitute dummy values and parse as XML
    dummy = (head_text + '\n' + pad_text + '\n' + tail_text)
    for tok, val in [
        ('@PRESET_PATH@',     '/tmp/Kit.adg'),
        ('@PRESET_PATH_REL@', 'Presets/Instruments/Drum Rack/Ablekit/Kit.adg'),
        ('@BRANCH_ID@',       '0'),
        ('@PAD_NAME@',        'Kick'),
        ('@SAMPLE_NAME@',     'Kick'),
        ('@SAMPLE_PATH@',     '/tmp/kick.wav'),
        ('@SAMPLE_PATH_REL@', 'Samples/Imported/Ablekit/kick.wav'),
        ('@RECEIVING_NOTE@',  '92'),
        ('@CHOKE_GROUP@',     '0'),
    ]:
        dummy = dummy.replace(tok, val)
    assert '@' not in dummy, f'Unreplaced token(s) in dummy: {set(re.findall(r"@[A-Z_]+@", dummy))}'
    try:
        ET.fromstring(dummy)
    except ET.ParseError as e:
        raise AssertionError(f'Round-trip XML parse failed: {e}') from e

    print('All assertions passed.')

    # ==================================================================
    # Write templates
    # ==================================================================
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / 'head.xml').write_text(head_text + '\n', encoding='utf-8')
    (DEST / 'pad.xml').write_text(pad_text + '\n',   encoding='utf-8')
    (DEST / 'tail.xml').write_text(tail_text + '\n', encoding='utf-8')
    for name in ('head', 'pad', 'tail'):
        print(f'wrote {DEST / name}.xml')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(f'Usage: {sys.argv[0]} <path/to/Drum Rack.adg>')
    build_templates(Path(sys.argv[1]).expanduser())
