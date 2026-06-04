import gzip
from pathlib import Path

import defusedxml.ElementTree as ET  # stdlib ET vulnerable to XXE/billion-laughs

from ablekit.adg import build_adg, render_kit_xml
from ablekit.models import Pad, Role, Sample


def make_pads() -> list[Pad]:
    kick = Sample(path=Path('/src/Kick A 1.wav'), role=Role.KICK, pad_name='Kick 1')
    hat = Sample(path=Path('/src/ClosedHH A.wav'), role=Role.CLOSED_HH, pad_name='Closed HH')
    return [Pad(note=36, sample=kick, choke=0), Pad(note=42, sample=hat, choke=1)]


def sample_paths():
    return {
        36: ('/lib/Samples/Imported/Ablekit/Exp/Kit/Kick A 1.wav',
             'Samples/Imported/Ablekit/Exp/Kit/Kick A 1.wav'),
        42: ('/lib/Samples/Imported/Ablekit/Exp/Kit/ClosedHH A.wav',
             'Samples/Imported/Ablekit/Exp/Kit/ClosedHH A.wav'),
    }


def test_render_is_valid_xml_with_inverted_notes_and_choke():
    xml = render_kit_xml(make_pads(), Path('/lib/Presets/Instruments/Drum Rack/Ablekit/Exp/Kit.adg'),
                         sample_paths())
    root = ET.fromstring(xml)
    assert root.tag == 'Ableton'
    zones = root.findall('.//ZoneSettings')
    received = [z.find('ReceivingNote').get('Value') for z in zones]
    assert received == ['92', '86']          # 128-36, 128-42
    chokes = [z.find('ChokeGroup').get('Value') for z in zones]
    assert chokes == ['0', '1']
    branches = root.findall('.//DrumBranchPreset')
    assert [b.get('Id') for b in branches] == ['0', '1']
    assert [b.find('Name').get('Value') for b in branches] == ['Kick 1', 'Closed HH']
    assert '@' not in xml  # every token substituted


def test_render_escapes_xml_specials():
    kick = Sample(path=Path('/src/K&B <Kick>.wav'), role=Role.KICK, pad_name='K&B <Kick>')
    pads = [Pad(note=36, sample=kick, choke=0)]
    paths = {36: ('/lib/Samples/K&B <Kick>.wav', 'Samples/K&B <Kick>.wav')}
    xml = render_kit_xml(pads, Path('/lib/Presets/Kit.adg'), paths)
    root = ET.fromstring(xml)  # would raise on unescaped & or <
    branch = root.find('.//DrumBranchPreset')
    assert branch.find('Name').get('Value') == 'K&B <Kick>'


def test_build_adg_gzip_roundtrip(tmp_path: Path):
    dest = tmp_path / 'out' / 'Kit.adg'
    build_adg(make_pads(), dest, sample_paths())
    raw = gzip.decompress(dest.read_bytes())
    assert raw.startswith(b'<?xml')
    ET.fromstring(raw)
