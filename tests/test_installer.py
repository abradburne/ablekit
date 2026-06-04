import gzip
from pathlib import Path

from ablekit.folderinfo import XMP_NAME
from ablekit.installer import install_kit
from ablekit.models import Pad, Role, Sample


def make_pads(tmp_path: Path) -> list[Pad]:
    src = tmp_path / 'src'
    src.mkdir(exist_ok=True)
    pads = []
    for note, name, role in [(36, 'Kick A 1.wav', Role.KICK),
                             (42, 'ClosedHH A.wav', Role.CLOSED_HH)]:
        f = src / name
        f.write_bytes(b'RIFFdata')
        pads.append(Pad(note=note,
                        sample=Sample(path=f, role=role, pad_name=name[:-4]),
                        choke=0))
    return pads


def test_install_kit_copies_samples_and_writes_adg(tmp_path: Path):
    lib = tmp_path / 'User Library'
    report = install_kit('Test Library', 'Akka Kit', make_pads(tmp_path), user_library=lib)

    adg = lib / 'Presets/Instruments/Drum Rack/Ablekit/Test Library/Akka Kit.adg'
    assert adg.exists()
    assert report.adg_path == adg
    assert report.sample_count == 2

    samples_dir = lib / 'Samples/Imported/Ablekit/Test Library/Akka Kit'
    assert sorted(p.name for p in samples_dir.iterdir() if p.is_file()) == ['ClosedHH A.wav', 'Kick A 1.wav']

    xml = gzip.decompress(adg.read_bytes()).decode()
    assert 'Samples/Imported/Ablekit/Test Library/Akka Kit/Kick A 1.wav' in xml
    assert str(samples_dir / 'Kick A 1.wav') in xml


def test_install_kit_writes_sample_sidecar(tmp_path: Path):
    lib = tmp_path / 'User Library'
    install_kit('Test Library', 'Akka Kit', make_pads(tmp_path), user_library=lib)

    samples_dir = lib / 'Samples/Imported/Ablekit/Test Library/Akka Kit'
    sidecar = samples_dir / 'Ableton Folder Info' / XMP_NAME
    assert sidecar.exists()
    content = sidecar.read_text()
    assert 'Kick A 1.wav' in content


def test_install_kit_dry_run_writes_nothing(tmp_path: Path):
    lib = tmp_path / 'User Library'
    report = install_kit('Test Library', 'Akka Kit', make_pads(tmp_path),
                         user_library=lib, dry_run=True)
    assert not lib.exists()
    assert report.sample_count == 2


def test_install_kit_dedupes_colliding_filenames(tmp_path: Path):
    src_a = tmp_path / 'a'
    src_b = tmp_path / 'b'
    src_a.mkdir()
    src_b.mkdir()
    (src_a / 'Hit.wav').write_bytes(b'A')
    (src_b / 'Hit.wav').write_bytes(b'B')
    pads = [
        Pad(note=36, sample=Sample(path=src_a / 'Hit.wav', role=Role.KICK, pad_name='Hit'), choke=0),
        Pad(note=37, sample=Sample(path=src_b / 'Hit.wav', role=Role.PERC, pad_name='Hit'), choke=0),
    ]
    lib = tmp_path / 'User Library'
    install_kit('Exp', 'Kit', pads, user_library=lib)
    samples_dir = lib / 'Samples/Imported/Ablekit/Exp/Kit'
    assert sorted(p.name for p in samples_dir.iterdir() if p.is_file()) == ['Hit 2.wav', 'Hit.wav']


def test_install_kit_overwrites_existing(tmp_path: Path):
    lib = tmp_path / 'User Library'
    pads = make_pads(tmp_path)
    install_kit('Exp', 'Kit', pads, user_library=lib)
    install_kit('Exp', 'Kit', pads, user_library=lib)  # idempotent re-run
    samples_dir = lib / 'Samples/Imported/Ablekit/Exp/Kit'
    assert len([p for p in samples_dir.iterdir() if p.is_file()]) == 2


def test_install_kit_dedupes_extensionless_filenames(tmp_path: Path):
    src_a = tmp_path / 'a'
    src_b = tmp_path / 'b'
    src_a.mkdir()
    src_b.mkdir()
    (src_a / 'Hit').write_bytes(b'A')
    (src_b / 'Hit').write_bytes(b'B')
    pads = [
        Pad(note=36, sample=Sample(path=src_a / 'Hit', role=Role.KICK, pad_name='Hit'), choke=0),
        Pad(note=37, sample=Sample(path=src_b / 'Hit', role=Role.PERC, pad_name='Hit'), choke=0),
    ]
    lib = tmp_path / 'User Library'
    install_kit('Exp', 'Kit', pads, user_library=lib)
    samples_dir = lib / 'Samples/Imported/Ablekit/Exp/Kit'
    assert sorted(p.name for p in samples_dir.iterdir() if p.is_file()) == ['Hit', 'Hit 2']
