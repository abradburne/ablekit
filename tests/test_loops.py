from __future__ import annotations

from pathlib import Path

import pytest

from ablekit.loops import install_loops, loop_filename, parse_loop
from ablekit.models import Role, Sample


# ---------------------------------------------------------------------------
# parse_loop
# ---------------------------------------------------------------------------

def test_parse_loop_drums_with_number():
    assert parse_loop('Drums[115] Akka 3') == ('Drums', 115, None, 3)


def test_parse_loop_full_with_key():
    assert parse_loop('Full[115] E Akka') == ('Full', 115, 'E', None)


def test_parse_loop_kick_with_number():
    assert parse_loop('Kick[120] Adrenalinn 1') == ('Kick', 120, None, 1)


def test_parse_loop_no_bpm_returns_none():
    assert parse_loop('no bpm here') is None


def test_parse_loop_perc_no_key_no_number():
    assert parse_loop('Perc[115] Akka') == ('Perc', 115, None, None)


def test_parse_loop_minor_key():
    assert parse_loop('Full[110] Fm SomeKit') == ('Full', 110, 'Fm', None)


def test_parse_loop_sharp_key():
    assert parse_loop('Loop[130] A# AnotherKit 2') == ('Loop', 130, 'A#', 2)


# ---------------------------------------------------------------------------
# loop_filename
# ---------------------------------------------------------------------------

def test_loop_filename_drums_kit_akka():
    assert loop_filename('Drums[115] Akka 3', '.wav', 'Akka Kit') == 'Akka Drums 3 115bpm.wav'


def test_loop_filename_full_with_key():
    assert loop_filename('Full[115] E Akka', '.wav', 'Akka Kit') == 'Akka Full E 115bpm.wav'


def test_loop_filename_perc_no_key_no_number():
    assert loop_filename('Perc[115] Akka', '.wav', 'Akka Kit') == 'Akka Perc 115bpm.wav'


def test_loop_filename_kick_adrenalinn():
    assert loop_filename('Kick[120] Adrenalinn 1', '.wav', 'AdrenaLinn Kit') == 'AdrenaLinn Kick 1 120bpm.wav'


def test_loop_filename_fallback_no_bpm():
    assert loop_filename('weird name Akka', '.wav', 'Akka Kit') == 'Akka weird name.wav'


def test_loop_filename_minor_key_preserved():
    # key token with minor suffix kept in filename
    result = loop_filename('Full[110] Fm SomeKit', '.wav', 'SomeKit Kit')
    assert result == 'SomeKit Full Fm 110bpm.wav'


def test_loop_filename_number_before_key_absent():
    # no trailing number and no key
    result = loop_filename('Rim[115] Akka', '.wav', 'Akka Kit')
    assert result == 'Akka Rim 115bpm.wav'


# ---------------------------------------------------------------------------
# install_loops
# ---------------------------------------------------------------------------

def _make_loop_sample(tmp_path: Path, name: str, role: Role = Role.LOOP) -> Sample:
    p = tmp_path / name
    p.write_bytes(b'RIFF')
    return Sample(path=p, role=role, pad_name=name)


def test_install_loops_copies_and_renames(tmp_path: Path):
    src_dir = tmp_path / 'src'
    src_dir.mkdir()
    loop1 = _make_loop_sample(src_dir, 'Drums[115] Akka 1.wav')
    loop2 = _make_loop_sample(src_dir, 'Full[115] E Akka.wav')

    lib = tmp_path / 'lib'
    count = install_loops('Test Library', 'Akka Kit', [loop1, loop2], lib, dry_run=False)

    assert count == 2
    loops_dir = lib / 'Samples' / 'Imported' / 'Ablekit' / 'Test Library' / 'Loops' / 'Akka'
    assert (loops_dir / 'Akka Drums 1 115bpm.wav').exists()
    assert (loops_dir / 'Akka Full E 115bpm.wav').exists()


def test_install_loops_writes_sidecar_with_type_loop(tmp_path: Path):
    from ablekit.folderinfo import FOLDER_INFO_DIR, XMP_NAME
    src_dir = tmp_path / 'src'
    src_dir.mkdir()
    loop1 = _make_loop_sample(src_dir, 'Full[115] E Akka.wav')

    lib = tmp_path / 'lib'
    install_loops('Test Library', 'Akka Kit', [loop1], lib, dry_run=False)

    loops_dir = lib / 'Samples' / 'Imported' / 'Ablekit' / 'Test Library' / 'Loops' / 'Akka'
    sidecar = loops_dir / FOLDER_INFO_DIR / XMP_NAME
    assert sidecar.exists()
    content = sidecar.read_text()
    assert 'Type|Loop' in content
    assert 'Creator|Native Instruments' in content
    assert 'Creator|Ablekit' in content
    assert 'Key|E' in content


def test_install_loops_sidecar_minor_key_tags(tmp_path: Path):
    from ablekit.folderinfo import FOLDER_INFO_DIR, XMP_NAME
    src_dir = tmp_path / 'src'
    src_dir.mkdir()
    loop1 = _make_loop_sample(src_dir, 'Full[110] Fm SomeKit.wav')

    lib = tmp_path / 'lib'
    install_loops('Test Library', 'SomeKit Kit', [loop1], lib, dry_run=False)

    loops_dir = lib / 'Samples' / 'Imported' / 'Ablekit' / 'Test Library' / 'Loops' / 'SomeKit'
    sidecar = loops_dir / FOLDER_INFO_DIR / XMP_NAME
    content = sidecar.read_text()
    assert 'Key|F' in content   # letter+accidental without 'm'
    assert 'Key|Minor' in content


def test_install_loops_dry_run_writes_nothing(tmp_path: Path):
    src_dir = tmp_path / 'src'
    src_dir.mkdir()
    loop1 = _make_loop_sample(src_dir, 'Drums[115] Akka 1.wav')

    lib = tmp_path / 'lib'
    count = install_loops('Test Library', 'Akka Kit', [loop1], lib, dry_run=True)

    assert count == 1
    assert not lib.exists()


def test_install_loops_dedup_collision(tmp_path: Path):
    """Two loops that would rename to the same filename get deduplicated."""
    src_dir = tmp_path / 'src'
    src_dir.mkdir()
    # Create two loops with the same parsed name (case variant) but different source paths
    loop1 = _make_loop_sample(src_dir, 'Drums[115] Akka 1.wav')
    loop2 = _make_loop_sample(src_dir, 'Drums[115] AKKA 1.wav')  # case variant, same parsed name

    lib = tmp_path / 'lib'
    # Both produce 'Akka Drums 1 115bpm.wav'; second must get a suffix like '_2'
    count = install_loops('Test Library', 'Akka Kit', [loop1, loop2], lib, dry_run=False)
    assert count == 2

    loops_dir = lib / 'Samples' / 'Imported' / 'Ablekit' / 'Test Library' / 'Loops' / 'Akka'
    files = sorted([f.name for f in loops_dir.iterdir() if f.is_file()])
    assert files == ['Akka Drums 1 115bpm 2.wav', 'Akka Drums 1 115bpm.wav']


def test_install_loops_empty_list_returns_zero(tmp_path: Path):
    lib = tmp_path / 'lib'
    count = install_loops('Test Library', 'Akka Kit', [], lib, dry_run=False)
    assert count == 0
    assert not lib.exists()


# ---------------------------------------------------------------------------
# convert integration: loop removed from rack, copied to Loops/ folder
# ---------------------------------------------------------------------------

def test_convert_loop_not_on_rack(fake_expansion: Path, tmp_path: Path):
    """The loop fixture file must NOT appear in the drum rack .adg."""
    import gzip
    import defusedxml.ElementTree as ET
    from ablekit.convert import convert_expansion
    from ablekit.scanner import scan_expansion

    lib = tmp_path / 'lib'
    exp = scan_expansion(fake_expansion)
    result = convert_expansion(exp, user_library=lib)

    akka = next(r for r in result.kits if r.kit_name == 'Akka Kit')
    raw = gzip.decompress(akka.adg_path.read_bytes())
    root = ET.fromstring(raw)
    branches = root.findall('.//DrumBranchPreset')
    # Akka kit has: 2 kicks, 1 snare, 1 ClosedHH, 1 OpenHH, 1 Crash, 1 Ride,
    # 1 Perc, 1 tonal synth = 9 rack samples; loop must NOT be among them
    assert len(branches) == 9

    # verify no branch references the loop wav name
    for ref in root.findall('.//SampleRef/FileRef/Path'):
        assert 'Drums[115] Akka 1' not in ref.get('Value', '')


def test_convert_loop_copied_to_loops_folder(fake_expansion: Path, tmp_path: Path):
    """The loop fixture must be renamed and placed under Loops/<KitBase>/."""
    from ablekit.convert import convert_expansion
    from ablekit.scanner import scan_expansion

    lib = tmp_path / 'lib'
    exp = scan_expansion(fake_expansion)
    convert_expansion(exp, user_library=lib)

    dest = (lib / 'Samples' / 'Imported' / 'Ablekit'
            / 'Test Library' / 'Loops' / 'Akka' / 'Akka Drums 1 115bpm.wav')
    assert dest.exists(), f'Expected loop at {dest}'


def test_convert_kit_report_loops_count(fake_expansion: Path, tmp_path: Path):
    """KitReport.loops must reflect the number of loops installed."""
    from ablekit.convert import convert_expansion
    from ablekit.scanner import scan_expansion

    lib = tmp_path / 'lib'
    exp = scan_expansion(fake_expansion)
    result = convert_expansion(exp, user_library=lib)

    akka = next(r for r in result.kits if r.kit_name == 'Akka Kit')
    assert akka.loops == 1

    about_us = next(r for r in result.kits if r.kit_name == 'About Us Kit')
    assert about_us.loops == 0


def test_convert_loop_dry_run_does_not_write_loops(fake_expansion: Path, tmp_path: Path):
    from ablekit.convert import convert_expansion
    from ablekit.scanner import scan_expansion

    lib = tmp_path / 'lib'
    exp = scan_expansion(fake_expansion)
    result = convert_expansion(exp, user_library=lib, dry_run=True)
    assert not lib.exists()
    akka = next(r for r in result.kits if r.kit_name == 'Akka Kit')
    assert akka.loops == 1
