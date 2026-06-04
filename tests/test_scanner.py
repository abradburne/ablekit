from pathlib import Path

from ablekit.scanner import discover, scan_expansion


def test_scan_expansion_finds_kits(fake_expansion: Path):
    exp = scan_expansion(fake_expansion)
    assert exp is not None
    assert exp.name == 'Test Library'
    assert exp.kit_names == ['About Us Kit', 'Akka Kit']


def test_scan_expansion_rejects_non_expansion(tmp_path: Path):
    (tmp_path / 'random').mkdir()
    assert scan_expansion(tmp_path / 'random') is None


def test_scan_expansion_rejects_groups_without_mxgrp(tmp_path: Path):
    root = tmp_path / 'Empty Library'
    (root / 'Groups').mkdir(parents=True)
    (root / 'Samples').mkdir()
    assert scan_expansion(root) is None


def test_discover_finds_expansions_and_skips_noise(fake_expansion: Path, tmp_path: Path):
    (tmp_path / 'Some Other Folder').mkdir()
    (tmp_path / 'a_file.txt').write_text('x')
    found = discover(tmp_path)
    assert [e.name for e in found] == ['Test Library']
