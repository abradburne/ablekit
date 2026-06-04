from pathlib import Path

import pytest


@pytest.fixture
def fake_expansion(tmp_path: Path) -> Path:
    root = tmp_path / 'Test Library'
    kits_dir = root / 'Groups' / 'Kits'
    kits_dir.mkdir(parents=True)
    for kit in ('Akka Kit', 'About Us Kit'):
        (kits_dir / f'{kit}.mxgrp').write_bytes(b'\x00')

    drum_files = [
        ('Kick', 'Kick Akka 1.wav'),
        ('Kick', 'Kick Akka 2.wav'),
        ('Kick', 'Kick AboutUs 1.wav'),
        ('Snare', 'Snare Akka 1.wav'),
        ('Snare', 'Rimshot AboutUs.wav'),
        ('HiHat', 'ClosedHH Akka.wav'),
        ('HiHat', 'OpenHH Akka.wav'),
        ('Cymbal', 'Crash Akka 1.wav'),
        ('Cymbal', 'Ride Akka.wav'),
        ('Percussion', 'Perc Akka 1.wav'),
        ('Percussion', 'Percussion AboutUs 5 .wav'),  # real NI dirt: trailing space
        ('Clap', 'Clap AboutUs.wav'),
        ('Shaker', 'Shaker Orphan 1.wav'),            # matches no kit
    ]
    for folder, name in drum_files:
        d = root / 'Samples' / 'Drums' / folder
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_bytes(b'RIFF')

    oneshot = root / 'Samples' / 'One Shots' / 'Synth Note'
    oneshot.mkdir(parents=True)
    (oneshot / 'Synth C Akka MSV.wav').write_bytes(b'RIFF')

    loops = root / 'Samples' / 'Loops' / 'Construction' / 'Akka'
    loops.mkdir(parents=True)
    (loops / 'Drums[115] Akka 1.wav').write_bytes(b'RIFF')

    # Instruments = multisample sets; must be ignored entirely
    inst = root / 'Samples' / 'Instruments' / 'Keys'
    inst.mkdir(parents=True)
    (inst / 'Key C Akka 1.wav').write_bytes(b'RIFF')

    return root
