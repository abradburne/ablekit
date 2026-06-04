from __future__ import annotations

import re
from difflib import SequenceMatcher
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


def _fuzzy_candidates(stem: str) -> list[str]:
    """Generate all contiguous word n-grams from a sample stem for fuzzy matching.

    Strips the leading category word (first word) and trailing key/number/MSV
    tokens, then returns all non-empty contiguous subsequences of remaining
    words joined without spaces (glued).

    Example: 'Synth Stailed Train A# MSV' -> ['StailedTrain', 'Stailed', 'Train']
    """
    words = stem.split()
    if not words:
        return []
    # Drop first word (category: 'Synth', 'Kick', 'Perc', ...)
    words = words[1:]
    # Drop trailing tokens that are numbers, musical keys, or 'MSV'
    _trailing = re.compile(r'^\d+$|^[A-G](#|b)?m?$|^MSV$', re.IGNORECASE)
    while words and _trailing.match(words[-1]):
        words.pop()
    if not words:
        return []
    candidates = []
    n = len(words)
    for length in range(n, 0, -1):
        for start in range(n - length + 1):
            chunk = words[start:start + length]
            glued = ''.join(chunk)
            if glued:
                candidates.append((glued, ' '.join(chunk)))
    # Return glued forms (unique, preserving order) along with their spaced originals
    # packed as (glued, spaced) — caller uses both
    seen: set[str] = set()
    result = []
    for glued, spaced in candidates:
        if glued not in seen:
            seen.add(glued)
            result.append((glued, spaced))
    return result


def match_expansion(exp: Expansion, fuzzy: bool = True) -> tuple[
        list[Kit], list[Path], list[Path], list[tuple[Path, str]]]:
    """Assign every audio file under Samples/ to a kit by name token.

    Tokens are matched case-insensitively against the path relative to
    Samples/ (loop folders carry the kit name too). Longest token first so
    e.g. 'NordicForest' cannot be claimed by a shorter overlapping token.
    A truncation fallback handles kits whose NI-stored token was shortened
    in the sample filenames (e.g. 'WhenIReachOut' -> 'WhenIReach').
    A final fuzzy pass (when fuzzy=True) assigns still-unmatched files to
    the closest kit by SequenceMatcher ratio, provided the best score is
    >= 0.84 and leads the second-best by >= 0.05.

    Returns (kits, unmatched, ignored, fuzzy_matches):
      - unmatched: classifiable audio files claimed by no kit token
      - ignored: audio where classify() returns None (e.g. Instruments/
        multisample sets that don't fit one-sample-per-pad); by design
      - fuzzy_matches: list of (path, kit_name) for fuzzy-assigned files
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

    # Fuzzy fallback: assign still-unmatched classifiable files to the closest
    # kit token using SequenceMatcher, provided the match is unambiguous.
    fuzzy_matches: list[tuple[Path, str]] = []
    if fuzzy:
        eligible_kits = [k for k in kits if k.token]
        still_unmatched = [p for p in classifiable if p not in claimed]
        for path in still_unmatched:
            cands = _fuzzy_candidates(path.stem)
            if not cands:
                continue
            scores: list[tuple[float, Kit, str]] = []  # (ratio, kit, spaced_form)
            for kit in eligible_kits:
                best_ratio = 0.0
                best_spaced = ''
                for glued, spaced in cands:
                    r = SequenceMatcher(None, glued.lower(), kit.token.lower()).ratio()
                    if r > best_ratio:
                        best_ratio = r
                        best_spaced = spaced
                scores.append((best_ratio, kit, best_spaced))
            scores.sort(key=lambda x: x[0], reverse=True)
            if not scores:
                continue
            best_ratio, best_kit, best_spaced = scores[0]
            second_ratio = scores[1][0] if len(scores) > 1 else 0.0
            if best_ratio >= 0.84 and (best_ratio - second_ratio) >= 0.05:
                # Strip the misspelled n-gram from stem before building pad_name
                clean_stem = re.sub(re.escape(best_spaced), '', path.stem,
                                    flags=re.IGNORECASE).strip()
                clean_stem = re.sub(r'\s+', ' ', clean_stem)
                claimed.add(path)
                best_kit.samples.append(
                    Sample(path=path, role=roles[path],
                           pad_name=pad_name(clean_stem, best_kit.name)))
                fuzzy_matches.append((path, best_kit.name))

    unmatched = [p for p in classifiable if p not in claimed]
    return kits, unmatched, ignored, fuzzy_matches
