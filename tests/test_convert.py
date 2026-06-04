from pathlib import Path

from ablekit.convert import convert_expansion
from ablekit.folderinfo import XMP_NAME
from ablekit.scanner import scan_expansion


def test_convert_expansion_end_to_end(fake_expansion: Path, tmp_path: Path):
    lib = tmp_path / 'User Library'
    exp = scan_expansion(fake_expansion)
    result = convert_expansion(exp, user_library=lib)

    assert result.expansion == 'Test Library'
    assert sorted(r.kit_name for r in result.kits) == ['About Us Kit', 'Akka Kit']
    assert result.skipped == []
    # Shaker Orphan: genuinely unmatched (no kit token)
    assert [p.name for p in result.unmatched] == ['Shaker Orphan 1.wav']
    # Key C Akka: Instruments/ folder — by-design ignored multisample
    assert result.ignored == 1
    for r in result.kits:
        assert r.adg_path.exists()


def test_convert_expansion_writes_kit_sidecar(fake_expansion: Path, tmp_path: Path):
    lib = tmp_path / 'User Library'
    exp = scan_expansion(fake_expansion)
    result = convert_expansion(exp, user_library=lib)

    # Kit sidecar lives beside the .adg files
    adg_dir = lib / 'Presets/Instruments/Drum Rack/Ablekit/Test Library'
    sidecar = adg_dir / 'Ableton Folder Info' / XMP_NAME
    assert sidecar.exists()
    content = sidecar.read_text()
    assert 'Akka Kit.adg' in content
    assert 'About Us Kit.adg' in content


def test_convert_expansion_dry_run_writes_nothing(fake_expansion: Path, tmp_path: Path):
    lib = tmp_path / 'User Library'
    exp = scan_expansion(fake_expansion)
    result = convert_expansion(exp, user_library=lib, dry_run=True)
    assert len(result.kits) == 2
    assert not lib.exists()


def test_convert_expansion_only_kits_filter(fake_expansion: Path, tmp_path: Path):
    lib = tmp_path / 'User Library'
    exp = scan_expansion(fake_expansion)
    result = convert_expansion(exp, user_library=lib, only_kits={'Akka Kit'})
    assert [r.kit_name for r in result.kits] == ['Akka Kit']


def test_convert_expansion_progress_callback(fake_expansion: Path, tmp_path: Path):
    seen: list[str] = []
    exp = scan_expansion(fake_expansion)
    convert_expansion(exp, user_library=tmp_path / 'lib', progress=seen.append)
    assert sorted(seen) == ['About Us Kit', 'Akka Kit']
