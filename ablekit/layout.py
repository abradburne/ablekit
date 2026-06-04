from __future__ import annotations

import re

from .models import HH_ROLES, Pad, Role, Sample

# GM-style fixed slots, iterated in priority order.
PRIMARY_SLOTS: dict[Role, list[int]] = {
    Role.KICK: [36],
    Role.RIM: [37],
    Role.SNARE: [38, 40],
    Role.CLAP: [39],
    Role.TOM: [41, 43, 45, 47, 48],
    Role.CLOSED_HH: [42],
    Role.PEDAL_HH: [44],
    Role.OPEN_HH: [46],
    Role.CRASH: [49, 50],
    Role.RIDE: [51],
}

MAX_NOTE = 127


def natural_key(text: str) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', text)]


def assign_pads(samples: list[Sample]) -> tuple[list[Pad], list[Sample]]:
    """Map a kit's samples to drum rack notes. Returns (pads, dropped).
    Note: loops are filtered out upstream by convert.py before calling this."""
    def named(role: Role) -> list[Sample]:
        return sorted((s for s in samples if s.role is role),
                      key=lambda s: natural_key(s.pad_name))

    pads: dict[int, Sample] = {}
    overflow: list[Sample] = []
    for role, slots in PRIMARY_SLOTS.items():
        queue = named(role)
        for note, sample in zip(slots, queue):
            pads[note] = sample
        overflow.extend(queue[len(slots):])

    dropped: list[Sample] = []
    empty_grid = [n for n in range(36, 52) if n not in pads]
    next_note = 52

    def place_above(sample: Sample) -> None:
        nonlocal next_note
        if next_note <= MAX_NOTE:
            pads[next_note] = sample
            next_note += 1
        else:
            dropped.append(sample)

    for sample in named(Role.PERC) + overflow:
        if empty_grid:
            pads[empty_grid.pop(0)] = sample
        else:
            place_above(sample)

    # tonal one-shots: always above the drum grid
    # (loops are filtered out upstream by convert.py)
    for sample in named(Role.TONAL):
        place_above(sample)

    result = [Pad(note=n, sample=s, choke=1 if s.role in HH_ROLES else 0)
              for n, s in sorted(pads.items())]
    return result, dropped
