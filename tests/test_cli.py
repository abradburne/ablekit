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
