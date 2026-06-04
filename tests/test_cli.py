from pathlib import Path

from ablekit.cli import main


def test_list_command(fake_expansion: Path, capsys):
    code = main(['list', '--root', str(fake_expansion.parent)])
    assert code == 0
    out = capsys.readouterr().out
    assert 'Test Library' in out
    assert '2 kits' in out


def test_convert_path(fake_expansion: Path, tmp_path: Path, capsys):
    lib = tmp_path / 'lib'
    code = main(['convert', str(fake_expansion), '--user-library', str(lib)])
    assert code == 0
    out = capsys.readouterr().out
    assert 'created 2 kits' in out
    assert (lib / 'Presets/Instruments/Drum Rack/Ablekit/Test Library/Akka Kit.adg').exists()


def test_convert_path_lists_unmatched(fake_expansion: Path, tmp_path: Path, capsys):
    lib = tmp_path / 'lib'
    code = main(['convert', str(fake_expansion), '--user-library', str(lib)])
    assert code == 0
    out = capsys.readouterr().out
    assert 'unmatched (NI naming quirks' in out
    assert 'Shaker Orphan 1.wav' in out


def test_convert_all(fake_expansion: Path, tmp_path: Path, capsys):
    lib = tmp_path / 'lib'
    code = main(['convert', '--all', '--root', str(fake_expansion.parent),
                 '--user-library', str(lib)])
    assert code == 0
    assert 'created 2 kits' in capsys.readouterr().out


def test_convert_dry_run(fake_expansion: Path, tmp_path: Path, capsys):
    lib = tmp_path / 'lib'
    code = main(['convert', str(fake_expansion), '--dry-run', '--user-library', str(lib)])
    assert code == 0
    assert 'would create 2 kits' in capsys.readouterr().out
    assert not lib.exists()


def test_convert_rejects_non_expansion(tmp_path: Path, capsys):
    (tmp_path / 'nope').mkdir()
    code = main(['convert', str(tmp_path / 'nope')])
    assert code == 1
    assert 'not a Maschine expansion' in capsys.readouterr().err


def test_convert_without_args_errors(capsys):
    code = main(['convert'])
    assert code == 1
    assert 'nothing to convert' in capsys.readouterr().err


def test_no_fuzzy_flag_accepted(fake_expansion: Path, tmp_path: Path, capsys):
    """--no-fuzzy is a valid flag; with the fixture it changes nothing (no typo files)."""
    lib = tmp_path / 'lib'
    code = main(['convert', str(fake_expansion), '--no-fuzzy', '--user-library', str(lib)])
    assert code == 0
    out = capsys.readouterr().out
    assert 'created 2 kits' in out


def test_fuzzy_listing_printed(tmp_path: Path, capsys):
    """CLI prints fuzzy-fixed section when fuzzy matches exist."""
    root = tmp_path / 'CH'
    one = root / 'Samples' / 'One Shots' / 'Synth Note'
    one.mkdir(parents=True)
    (one / 'Synth Stailed Train A MSV.wav').write_bytes(b'RIFF')
    kits_dir = root / 'Groups' / 'Kits'
    kits_dir.mkdir(parents=True)
    (kits_dir / 'Stalled Train Kit.mxgrp').write_bytes(b'\x00')
    lib = tmp_path / 'lib'
    code = main(['convert', str(root), '--dry-run', '--user-library', str(lib)])
    assert code == 0
    out = capsys.readouterr().out
    assert 'fuzzy-fixed' in out
    assert 'Stalled Train Kit' in out
    assert 'Synth Stailed Train A MSV.wav' in out
