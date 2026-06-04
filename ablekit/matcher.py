from __future__ import annotations

import re
from pathlib import Path

from .models import Expansion, Kit, Role, Sample

AUDIO_EXTS = {'.wav', '.aif', '.aiff', '.flac', '.mp3'}

# Filename prefix overrides, checked against the start of the lowercased stem.
# Order matters: longest/most-specific first.
PREFIX_ROLES = [
    ('closedhh', Role.CLOSED_HH),
    ('openhh', Role.OPEN_HH),
    ('pedalhh', Role.PEDAL_HH),
    ('rimshot', Role.RIM),
    ('rim ', Role.RIM),
    ('crash', Role.CRASH),
    ('ride', Role.RIDE),
]

FOLDER_ROLES = {
    'kick': Role.KICK,
    'snare': Role.SNARE,
    'hihat': Role.CLOSED_HH,
    'clap': Role.CLAP,
    'cymbal': Role.CRASH,
    'tom': Role.TOM,
    'percussion': Role.PERC,
    'perc': Role.PERC,
    'shaker': Role.PERC,
    'tambourine': Role.PERC,
}


def kit_token(kit_name: str) -> str:
    """'About Us Kit' -> 'AboutUs' (NI strips spaces in sample names).

    A file named exactly 'Kit.mxgrp' has no meaningful prefix, so we return
    '' in that case.  The match_expansion loop skips kits with an empty token
    so they cannot greedily claim every sample file.
    Suffix stripping is case-insensitive to handle NI typos like 'Falke KIt'.
    """
    base = re.sub(r'\s*kit$', '', kit_name, flags=re.IGNORECASE).strip()
    return re.sub(r'\s+', '', base)


def _name_alternation(kit_name: str) -> str:
    """Regex alternation matching the kit's token or spaced base form.

    >>> _name_alternation('Edge Drum Kit')
    'Edge\\ Drum|EdgeDrum'
    >>> _name_alternation('Akka Kit')
    'Akka'
    """
    base = re.sub(r'\s*kit$', '', kit_name, flags=re.IGNORECASE).strip()
    token = re.sub(r'\s+', '', base)
    alts = {re.escape(token), re.escape(base)} - {''}
    return '|'.join(sorted(alts, key=len, reverse=True))


def kit_pattern(kit_name: str) -> re.Pattern[str]:
    """Case-insensitive pattern for a kit's name inside sample filenames.

    Matches the space-stripped token ('ThirdEye') or the spaced base form
    ('Third Eye'), tolerating NI dirt: optional plural 's' and digits glued
    directly to the name ('WhiteRoom1'). (?<!\\w) stops mid-word matches.
    Returns a never-matching pattern when the kit name yields no alternation
    (e.g. a kit named exactly 'Kit').
    """
    body = _name_alternation(kit_name)
    if not body:
        return re.compile(r'(?!)')  # never matches
    return re.compile(rf'(?<!\w)(?:{body})s?(?![A-Za-z])', re.IGNORECASE)


def _truncations(token: str) -> list[str]:
    """'WhenIReachOut' -> ['WhenIReach'] (drop trailing camel words).

    Note: the regex [A-Z]+[a-z]* merges consecutive uppercase letters, so
    'WhenIReachOut' is tokenised as ['When', 'IReach', 'Out'] and produces
    only ['WhenIReach'], not ['WhenIReach', 'WhenI'].
    """
    words = re.findall(r'[A-Z]+[a-z]*|[a-z]+|\d+', token)
    out = []
    for n in range(len(words) - 1, 0, -1):
        cand = ''.join(words[:n])
        if len(cand) >= 6:
            out.append(cand)
    return out


def pad_name(stem: str, kit_name: str) -> str:
    """Display label: remove kit name (token or spaced form), split CamelCase.

    kit_name may be the full display name ('Edge Drum Kit') or a bare camel
    token ('EdgeDrum'); _name_alternation handles both.
    """
    alt = _name_alternation(kit_name)
    if alt:
        name = re.sub(rf'\s*(?<!\w)(?:{alt})\s*', ' ', stem,
                      flags=re.IGNORECASE).strip()
    else:
        name = stem.strip()
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', name)
    return name or stem.strip()


def classify(samples_root: Path, path: Path) -> Role | None:
    """Role from folder position + filename prefix. None = ignore the file
    (Instruments/ and other multisample folders don't fit one-sample-per-pad)."""
    rel = path.relative_to(samples_root).parts
    top = rel[0].lower()
    if top == 'loops':
        return Role.LOOP
    if top == 'one shots':
        return Role.TONAL
    if top != 'drums':
        return None
    stem = path.stem.lower()
    for prefix, role in PREFIX_ROLES:
        if stem.startswith(prefix):
            return role
    folder = rel[1].lower() if len(rel) > 2 else ''
    return FOLDER_ROLES.get(folder, Role.PERC)


def match_expansion(exp: Expansion) -> tuple[list[Kit], list[Path], list[Path]]:
    """Assign every audio file under Samples/ to a kit by name token.

    Tokens are matched case-insensitively against the path relative to
    Samples/ (loop folders carry the kit name too). Longest token first so
    e.g. 'NordicForest' cannot be claimed by a shorter overlapping token.
    A truncation fallback handles kits whose NI-stored token was shortened
    in the sample filenames (e.g. 'WhenIReachOut' -> 'WhenIReach').

    Returns (kits, unmatched, ignored):
      - unmatched: classifiable audio files claimed by no kit token
      - ignored: audio where classify() returns None (e.g. Instruments/
        multisample sets that don't fit one-sample-per-pad); by design
    """
    samples_root = exp.path / 'Samples'
    audio = [p for p in sorted(samples_root.rglob('*'))
             if p.suffix.lower() in AUDIO_EXTS]
    kits = [Kit(name=n, token=kit_token(n)) for n in exp.kit_names]

    # Pre-classify all audio once: path -> role|None.
    # Files where classify() returns None are by-design ignored (Instruments/
    # multisample folders etc.) and are never offered to the match loop.
    roles: dict[Path, Role | None] = {p: classify(samples_root, p) for p in audio}
    ignored = [p for p, role in roles.items() if role is None]
    classifiable = [p for p in audio if roles[p] is not None]

    claimed: set[Path] = set()

    # Main pass: longest token first to prevent shorter tokens stealing matches.
    for kit in sorted(kits, key=lambda k: len(k.token), reverse=True):
        if not kit.token:
            continue
        pattern = kit_pattern(kit.name)
        for path in classifiable:
            if path in claimed:
                continue
            if not pattern.search(str(path.relative_to(samples_root))):
                continue
            role = roles[path]
            claimed.add(path)
            kit.samples.append(
                Sample(path=path, role=role, pad_name=pad_name(path.stem, kit.name)))

    # Truncation fallback: kits that still have zero samples after the main
    # pass may have been stored by NI with a shortened token in filenames.
    # Try progressively dropping trailing CamelCase words until a match is found.
    empty_kits = sorted(
        [k for k in kits if not k.samples and k.token],
        key=lambda k: len(k.token),
        reverse=True,
    )
    for kit in empty_kits:
        for cand in _truncations(kit.token):
            pat = re.compile(
                rf'(?<!\w){re.escape(cand)}s?(?![A-Za-z])', re.IGNORECASE)
            matches = [p for p in classifiable
                       if p not in claimed and pat.search(
                           str(p.relative_to(samples_root)))]
            if matches:
                for path in matches:
                    claimed.add(path)
                    kit.samples.append(
                        Sample(path=path, role=roles[path],
                               pad_name=pad_name(path.stem, cand)))
                break  # first truncation that yielded matches wins

    unmatched = [p for p in classifiable if p not in claimed]
    return kits, unmatched, ignored
