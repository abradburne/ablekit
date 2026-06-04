from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Role(Enum):
    KICK = 'kick'
    RIM = 'rim'
    SNARE = 'snare'
    CLAP = 'clap'
    CLOSED_HH = 'closed_hh'
    PEDAL_HH = 'pedal_hh'
    OPEN_HH = 'open_hh'
    TOM = 'tom'
    CRASH = 'crash'
    RIDE = 'ride'
    PERC = 'perc'
    TONAL = 'tonal'
    LOOP = 'loop'


HH_ROLES = {Role.CLOSED_HH, Role.PEDAL_HH, Role.OPEN_HH}


@dataclass
class Sample:
    path: Path      # absolute path to the source audio file
    role: Role
    pad_name: str   # display label, kit token removed


@dataclass
class Kit:
    name: str       # 'Akka Kit'
    token: str      # 'Akka'
    samples: list[Sample] = field(default_factory=list)


@dataclass
class Expansion:
    name: str       # 'Polar Flare Library'
    path: Path
    kit_names: list[str] = field(default_factory=list)


@dataclass
class Pad:
    note: int       # MIDI note, 36 = C1 = bottom-left pad
    sample: Sample
    choke: int      # 0 = no choke, 1 = hi-hat choke group
