import gzip
from pathlib import Path

import defusedxml.ElementTree as ET  # stdlib ET vulnerable to XXE/billion-laughs
import pytest

from ablekit.convert import convert_expansion
from ablekit.scanner import scan_expansion

POLAR = Path('/Users/Shared/Polar Flare Library')

pytestmark = pytest.mark.skipif(not POLAR.exists(), reason='Polar Flare not installed')


def test_convert_polar_flare_against_tmp_library(tmp_path: Path):
    exp = scan_expansion(POLAR)
    assert exp is not None
    result = convert_expansion(exp, user_library=tmp_path)

    assert len(result.kits) == 40
    assert result.skipped == []
    assert len(result.unmatched) == 9     # genuinely unmatched (no kit token matched)
    assert all('NorthernForest' in p.name for p in result.unmatched)
    assert result.ignored == 134     # Instruments/ multisample sets — by design

    akka = next(r for r in result.kits if r.kit_name == 'Akka Kit')
    raw = gzip.decompress(akka.adg_path.read_bytes())
    root = ET.fromstring(raw)

    branches = root.findall('.//DrumBranchPreset')
    assert len(branches) >= 14  # 2 kicks, 2 snares, 2 hats, 6 percs, 3 cymbals...

    # kick on pad C1: ReceivingNote inverted = 128 - 36
    received = {int(z.find('ReceivingNote').get('Value'))
                for z in root.findall('.//ZoneSettings')}
    assert 92 in received

    # hi-hat choke group present
    chokes = {z.find('ChokeGroup').get('Value')
              for z in root.findall('.//ZoneSettings')}
    assert '1' in chokes

    # every referenced sample file was copied and exists
    for branch in branches:
        for ref in branch.findall('.//SampleRef/FileRef/Path'):
            assert Path(ref.get('Value')).exists(), ref.get('Value')
