from pathlib import Path

import defusedxml.ElementTree as ET

from ablekit.folderinfo import XMP_NAME, sample_tags, write_folder_info
from ablekit.models import Role

NS = {
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'ablFR': 'https://ns.ableton.com/xmp/fs-resources/1.0/',
}


def test_sample_tags_by_role():
    assert sample_tags(Role.KICK) == ['Drums|Kick', 'Type|One Shot', 'Creator|Ablekit']
    assert sample_tags(Role.LOOP) == ['Type|Loop', 'Creator|Ablekit']
    assert sample_tags(Role.TONAL) == ['Type|One Shot', 'Creator|Ablekit']
    assert sample_tags(Role.CLOSED_HH)[0] == 'Drums|Hihat|Closed Hihat'


def test_write_folder_info_valid_xmp(tmp_path: Path):
    dest = write_folder_info(tmp_path, {'Kick A & B.wav': ['Drums|Kick', 'Creator|Ablekit']})
    assert dest == tmp_path / 'Ableton Folder Info' / XMP_NAME
    root = ET.parse(dest).getroot()
    paths = [e.text for e in root.iter('{https://ns.ableton.com/xmp/fs-resources/1.0/}filePath')]
    assert paths == ['Kick A & B.wav']
    keywords = [e.text for e in root.iter('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li')
                if e.text and '|' in e.text]
    assert 'Drums|Kick' in keywords


def test_write_folder_info_creates_dir(tmp_path: Path):
    folder = tmp_path / 'deep' / 'nested'
    folder.mkdir(parents=True)
    dest = write_folder_info(folder, {'sample.wav': ['Type|One Shot', 'Creator|Ablekit']})
    assert dest.exists()
    assert (folder / 'Ableton Folder Info').is_dir()


def test_write_folder_info_multiple_items(tmp_path: Path):
    items = {
        'Kick.wav': ['Drums|Kick', 'Type|One Shot', 'Creator|Ablekit'],
        'Snare.wav': ['Drums|Snare|Snare Hit', 'Type|One Shot', 'Creator|Ablekit'],
    }
    dest = write_folder_info(tmp_path, items)
    root = ET.parse(dest).getroot()
    paths = [e.text for e in root.iter('{https://ns.ableton.com/xmp/fs-resources/1.0/}filePath')]
    assert sorted(paths) == ['Kick.wav', 'Snare.wav']


def test_write_folder_info_ampersand_escaped(tmp_path: Path):
    dest = write_folder_info(tmp_path, {'A & B.wav': ['Creator|Ablekit']})
    # If XML is valid (parseable), ampersand was properly escaped
    root = ET.parse(dest).getroot()
    paths = [e.text for e in root.iter('{https://ns.ableton.com/xmp/fs-resources/1.0/}filePath')]
    assert paths == ['A & B.wav']
