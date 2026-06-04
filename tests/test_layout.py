from pathlib import Path

from ablekit.layout import assign_pads
from ablekit.models import Role, Sample


def s(name: str, role: Role) -> Sample:
    return Sample(path=Path(f'/x/{name}.wav'), role=role, pad_name=name)


def by_note(pads):
    return {p.note: p for p in pads}


def test_gm_slot_assignment():
    pads, dropped = assign_pads([
        s('Kick 1', Role.KICK),
        s('Snare 1', Role.SNARE),
        s('Snare 2', Role.SNARE),
        s('Clap', Role.CLAP),
        s('Closed HH', Role.CLOSED_HH),
        s('Open HH', Role.OPEN_HH),
        s('Crash 1', Role.CRASH),
        s('Ride', Role.RIDE),
    ])
    assert dropped == []
    notes = by_note(pads)
    assert notes[36].sample.pad_name == 'Kick 1'
    assert notes[38].sample.pad_name == 'Snare 1'
    assert notes[40].sample.pad_name == 'Snare 2'
    assert notes[39].sample.pad_name == 'Clap'
    assert notes[42].sample.pad_name == 'Closed HH'
    assert notes[46].sample.pad_name == 'Open HH'
    assert notes[49].sample.pad_name == 'Crash 1'
    assert notes[51].sample.pad_name == 'Ride'


def test_hh_choke_group_everywhere_others_zero():
    pads, _ = assign_pads([
        s('Kick 1', Role.KICK),
        s('Closed HH', Role.CLOSED_HH),
        s('Open HH', Role.OPEN_HH),
        s('Pedal HH', Role.PEDAL_HH),
    ])
    chokes = {p.sample.pad_name: p.choke for p in pads}
    assert chokes == {'Kick 1': 0, 'Closed HH': 1, 'Open HH': 1, 'Pedal HH': 1}


def test_percs_fill_empty_grid_slots_ascending():
    pads, _ = assign_pads([
        s('Kick 1', Role.KICK),
        s('Perc 1', Role.PERC),
        s('Perc 2', Role.PERC),
    ])
    notes = by_note(pads)
    assert notes[36].sample.pad_name == 'Kick 1'
    # first two empty slots after 36 are 37 and 38
    assert notes[37].sample.pad_name == 'Perc 1'
    assert notes[38].sample.pad_name == 'Perc 2'


def test_role_overflow_joins_fill_queue_after_percs():
    pads, _ = assign_pads([
        s('Kick 1', Role.KICK),
        s('Kick 2', Role.KICK),     # overflow: only one kick slot
        s('Perc 1', Role.PERC),
    ])
    notes = by_note(pads)
    assert notes[36].sample.pad_name == 'Kick 1'
    assert notes[37].sample.pad_name == 'Perc 1'
    assert notes[38].sample.pad_name == 'Kick 2'


def test_natural_sort_picks_kick_2_before_kick_10():
    pads, _ = assign_pads([
        s('Kick 10', Role.KICK),
        s('Kick 2', Role.KICK),
    ])
    notes = by_note(pads)
    assert notes[36].sample.pad_name == 'Kick 2'


def test_tonals_go_above_grid_never_backfill():
    pads, _ = assign_pads([
        s('Kick 1', Role.KICK),
        s('Synth C', Role.TONAL),
        s('Synth D', Role.TONAL),
    ])
    notes = by_note(pads)
    assert notes[36].sample.pad_name == 'Kick 1'
    assert notes[52].sample.pad_name == 'Synth C'
    assert notes[53].sample.pad_name == 'Synth D'
    assert 37 not in notes


def test_overflow_past_127_is_dropped():
    many = [s(f'Tonal {i:03d}', Role.TONAL) for i in range(80)]
    pads, dropped = assign_pads([s('Kick 1', Role.KICK)] + many)
    assert max(p.note for p in pads) == 127
    # notes 52..127 hold 76 tonals; 4 dropped
    assert len(dropped) == 4
