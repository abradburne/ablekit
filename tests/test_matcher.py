from pathlib import Path

from ablekit.matcher import kit_token, match_expansion, pad_name
from ablekit.models import Role
from ablekit.scanner import scan_expansion


def test_kit_token():
    assert kit_token('Akka Kit') == 'Akka'
    assert kit_token('About Us Kit') == 'AboutUs'
    assert kit_token('Lulu Roed Kit') == 'LuluRoed'
    assert kit_token('Nordic Forest Kit') == 'NordicForest'
    assert kit_token('Kit') == ''


def test_pad_name_strips_token_and_splits_camel():
    assert pad_name('Kick Akka 1', 'Akka') == 'Kick 1'
    assert pad_name('ClosedHH Akka', 'Akka') == 'Closed HH'
    assert pad_name('Synth C Akka MSV', 'Akka') == 'Synth C MSV'
    assert pad_name('Percussion AboutUs 5 ', 'AboutUs') == 'Percussion 5'


def kit_named(kits, name):
    return next(k for k in kits if k.name == name)


def test_match_expansion_assigns_samples_to_kits(fake_expansion: Path):
    exp = scan_expansion(fake_expansion)
    kits, unmatched, ignored = match_expansion(exp)

    akka = kit_named(kits, 'Akka Kit')
    names = sorted(s.path.name for s in akka.samples)
    assert names == [
        'ClosedHH Akka.wav',
        'Crash Akka 1.wav',
        'Drums[115] Akka 1.wav',
        'Kick Akka 1.wav',
        'Kick Akka 2.wav',
        'OpenHH Akka.wav',
        'Perc Akka 1.wav',
        'Ride Akka.wav',
        'Snare Akka 1.wav',
        'Synth C Akka MSV.wav',
    ]

    about = kit_named(kits, 'About Us Kit')
    about_names = sorted(s.path.name for s in about.samples)
    assert about_names == [
        'Clap AboutUs.wav',
        'Kick AboutUs 1.wav',
        'Percussion AboutUs 5 .wav',
        'Rimshot AboutUs.wav',
    ]


def test_match_expansion_classifies_roles(fake_expansion: Path):
    exp = scan_expansion(fake_expansion)
    kits, _, _ignored = match_expansion(exp)
    akka = kit_named(kits, 'Akka Kit')
    roles = {s.path.name: s.role for s in akka.samples}
    assert roles['Kick Akka 1.wav'] is Role.KICK
    assert roles['ClosedHH Akka.wav'] is Role.CLOSED_HH
    assert roles['OpenHH Akka.wav'] is Role.OPEN_HH
    assert roles['Crash Akka 1.wav'] is Role.CRASH
    assert roles['Ride Akka.wav'] is Role.RIDE
    assert roles['Perc Akka 1.wav'] is Role.PERC
    assert roles['Synth C Akka MSV.wav'] is Role.TONAL
    assert roles['Drums[115] Akka 1.wav'] is Role.LOOP

    about = kit_named(kits, 'About Us Kit')
    about_roles = {s.path.name: s.role for s in about.samples}
    assert about_roles['Rimshot AboutUs.wav'] is Role.RIM
    assert about_roles['Clap AboutUs.wav'] is Role.CLAP


def test_match_expansion_separates_unmatched_from_ignored(fake_expansion: Path):
    """Instruments audio (classify→None) goes to ignored; no-kit-match goes to unmatched."""
    exp = scan_expansion(fake_expansion)
    kits, unmatched, ignored = match_expansion(exp)
    unmatched_names = sorted(p.name for p in unmatched)
    ignored_names = sorted(p.name for p in ignored)
    # Shaker matches no kit token — genuinely unmatched
    assert unmatched_names == ['Shaker Orphan 1.wav']
    # Key C Akka lives in Instruments/ — classify() returns None, by design ignored
    assert ignored_names == ['Key C Akka 1.wav']
    for kit in kits:
        assert all('Key C' not in s.path.name for s in kit.samples)


def test_match_expansion_skips_empty_token_kit(fake_expansion: Path):
    from ablekit.models import Expansion
    exp = Expansion(name='Test Library', path=fake_expansion, kit_names=['Kit'])
    kits, unmatched, ignored = match_expansion(exp)
    assert kits[0].samples == []          # empty token claims nothing
    assert len(unmatched) > 0
    assert len(ignored) > 0              # Instruments/ files are always ignored


def test_kit_token_case_insensitive_suffix():
    assert kit_token('Falke KIt') == 'Falke'
    assert kit_token('Akka kit') == 'Akka'


def test_match_case_insensitive_and_spaced_forms(tmp_path: Path):
    from ablekit.models import Expansion
    root = tmp_path / 'CH'
    drums = root / 'Samples' / 'Drums' / 'Kick'
    drums.mkdir(parents=True)
    for name in ('Kick Adrenalinn 1.wav',     # kit 'AdrenaLinn Kit' (case)
                 'Kick CInch 3.wav',          # kit 'Cinch Kit' (case)
                 'Kick EdgeDrums.wav',        # kit 'Edge Drum Kit' (plural)
                 'Kick Edge Drum 3.wav',      # spaced form
                 'Kick WhiteRoom1.wav'):      # glued digit
        (drums / name).write_bytes(b'RIFF')
    exp = Expansion(name='CH', path=root,
                    kit_names=['AdrenaLinn Kit', 'Cinch Kit', 'Edge Drum Kit', 'White Room Kit'])
    kits, unmatched, ignored = match_expansion(exp)
    by = {k.name: sorted(s.path.name for s in k.samples) for k in kits}
    assert by['AdrenaLinn Kit'] == ['Kick Adrenalinn 1.wav']
    assert by['Cinch Kit'] == ['Kick CInch 3.wav']
    assert by['Edge Drum Kit'] == ['Kick Edge Drum 3.wav', 'Kick EdgeDrums.wav']
    assert by['White Room Kit'] == ['Kick WhiteRoom1.wav']
    assert unmatched == []
    assert ignored == []


def test_match_truncated_token_fallback(tmp_path: Path):
    from ablekit.models import Expansion
    root = tmp_path / 'PF'
    vox = root / 'Samples' / 'One Shots' / 'Vocal'
    vox.mkdir(parents=True)
    (vox / 'Vox WhenIReach 9.wav').write_bytes(b'RIFF')
    (root / 'Samples' / 'Drums' / 'Kick').mkdir(parents=True)
    (root / 'Samples' / 'Drums' / 'Kick' / 'Kick Akka 1.wav').write_bytes(b'RIFF')
    exp = Expansion(name='PF', path=root,
                    kit_names=['Akka Kit', 'When I Reach Out Kit'])
    kits, unmatched, ignored = match_expansion(exp)
    by = {k.name: [s.path.name for s in k.samples] for k in kits}
    assert by['When I Reach Out Kit'] == ['Vox WhenIReach 9.wav']
    assert by['Akka Kit'] == ['Kick Akka 1.wav']
    assert unmatched == []
    assert ignored == []


def test_pad_name_case_insensitive_token_removal():
    assert pad_name('Kick Adrenalinn 1', 'AdrenaLinn') == 'Kick 1'


def test_pad_name_strips_spaced_form():
    assert pad_name('Kick Edge Drum 3', 'Edge Drum Kit') == 'Kick 3'
    assert pad_name('Synth Third Eye 1 MSV', 'Third Eye Kit') == 'Synth 1 MSV'


def test_kit_pattern_bare_kit_matches_nothing():
    from ablekit.matcher import kit_pattern
    assert kit_pattern('Kit').search('Kick 1.wav') is None
