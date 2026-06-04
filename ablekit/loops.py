"""Loop installation: rename, copy, and tag construction loops.

Loops are never placed on the drum rack. Instead they are copied to
  User Library/Samples/Imported/Ablekit/<Expansion>/Loops/<KitBase>/
renamed to  '<KitBase> <Part> [<n>] [<Key>] <bpm>bpm<suffix>'
and tagged with Type|Loop, Creator|Ablekit, and Key tags in a sidecar.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from .folderinfo import CREATOR_TAG, NI_TAG, write_folder_info
from .models import Sample

# Matches the mandatory '<Part>[<bpm>]' prefix of a loop stem.
_BPM_RE = re.compile(r'^([A-Za-z]+)\[(\d+)\]\s*(.*)', re.DOTALL)

# Matches an optional key token: single letter A-G, optional accidental, optional minor 'm'.
_KEY_RE = re.compile(r'^[A-G](#|b)?m?$')

_LOOP_TAGS_BASE = ['Type|Loop', NI_TAG, CREATOR_TAG]


def _kit_base(kit_name: str) -> str:
    """'Akka Kit' -> 'Akka', 'About Us Kit' -> 'About Us'."""
    return re.sub(r'\s*kit$', '', kit_name, flags=re.IGNORECASE).strip()


def _name_alternation(kit_name: str) -> str:
    """Return a regex alternation matching the kit token or spaced base form.

    Mirrors matcher._name_alternation so we strip the same tokens.
    """
    base = re.sub(r'\s*kit$', '', kit_name, flags=re.IGNORECASE).strip()
    token = re.sub(r'\s+', '', base)
    alts = {re.escape(token), re.escape(base)} - {''}
    return '|'.join(sorted(alts, key=len, reverse=True))


def parse_loop(stem: str) -> tuple[str, int, str | None, int | None] | None:
    """Parse a loop stem into (part, bpm, key, n).

    Returns None when the stem does not match the '<Part>[<bpm>]' pattern.

    Examples
    --------
    >>> parse_loop('Drums[115] Akka 3')
    ('Drums', 115, None, 3)
    >>> parse_loop('Full[115] E Akka')
    ('Full', 115, 'E', None)
    >>> parse_loop('no bpm here')
    """
    m = _BPM_RE.match(stem)
    if not m:
        return None
    part = m.group(1)
    bpm = int(m.group(2))
    rest_tokens = m.group(3).split()

    # Detect trailing integer
    n: int | None = None
    if rest_tokens and rest_tokens[-1].isdigit():
        n = int(rest_tokens.pop())

    # Detect key among remaining tokens (any single token matching the key pattern)
    key: str | None = None
    for i, tok in enumerate(rest_tokens):
        if _KEY_RE.match(tok):
            key = tok
            rest_tokens.pop(i)
            break

    return part, bpm, key, n


def loop_filename(stem: str, suffix: str, kit_name: str) -> str:
    """Return the renamed filename for a loop sample.

    Format: '<KitBase> <Part> [<n>] [<Key>] <bpm>bpm<suffix>'
    Absent parts are omitted; tokens are single-space separated.

    Falls back to '<KitBase> <stem-with-kit-token-stripped><suffix>' when
    the stem does not contain a '[bpm]' expression.

    Examples
    --------
    >>> loop_filename('Drums[115] Akka 3', '.wav', 'Akka Kit')
    'Akka Drums 3 115bpm.wav'
    >>> loop_filename('Full[115] E Akka', '.wav', 'Akka Kit')
    'Akka Full E 115bpm.wav'
    >>> loop_filename('weird name Akka', '.wav', 'Akka Kit')
    'Akka weird name.wav'
    """
    kit_base = _kit_base(kit_name)
    alt = _name_alternation(kit_name)

    parsed = parse_loop(stem)
    if parsed is None:
        # Fallback: strip kit token and return plain rename
        if alt:
            cleaned = re.sub(rf'\s*(?<!\w)(?:{alt})\s*', ' ', stem,
                             flags=re.IGNORECASE).strip()
        else:
            cleaned = stem.strip()
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return f'{kit_base} {cleaned}{suffix}'

    part, bpm, key, n = parsed

    # Build ordered token list: KitBase Part [n] [Key] bpm
    tokens = [kit_base, part]
    if n is not None:
        tokens.append(str(n))
    if key is not None:
        tokens.append(key)
    tokens.append(f'{bpm}bpm')

    return ' '.join(tokens) + suffix


def _loop_tags(key: str | None) -> list[str]:
    """Build the tag list for a loop: Type|Loop, Creator|Ablekit, Key tags."""
    tags = list(_LOOP_TAGS_BASE)
    if key is not None:
        is_minor = key.endswith('m')
        # Strip the 'm' suffix for the letter+accidental tag
        letter_acc = key[:-1] if is_minor else key
        tags.append(f'Key|{letter_acc}')
        if is_minor:
            tags.append('Key|Minor')
    return tags


def install_loops(expansion_name: str, kit_name: str, loops: list[Sample],
                  user_library: Path, dry_run: bool = False) -> int:
    """Copy and rename loop samples into the User Library Loops folder.

    Returns the count of loops processed (same whether dry_run or not).
    Writes a Live 12 tag sidecar (folderinfo XMP) for the kit's loop folder
    unless dry_run is True.
    """
    if not loops:
        return 0

    kit_base = _kit_base(kit_name)
    loops_dir = (user_library / 'Samples' / 'Imported' / 'Ablekit'
                 / expansion_name / 'Loops' / kit_base)

    copies: list[tuple[Path, Path, list[str]]] = []  # (src, dest, tags)
    used_names: set[str] = set()

    for sample in loops:
        stem = sample.path.stem
        suffix = sample.path.suffix
        dest_name = loop_filename(stem, suffix, kit_name)

        # Dedup: if the name collides, append a numeric suffix
        if dest_name in used_names:
            base_stem = Path(dest_name).stem
            ext = Path(dest_name).suffix
            counter = 2
            while f'{base_stem} {counter}{ext}' in used_names:
                counter += 1
            dest_name = f'{base_stem} {counter}{ext}'

        used_names.add(dest_name)
        dest = loops_dir / dest_name

        # Determine key from stem for tags
        parsed = parse_loop(stem)
        key = parsed[2] if parsed is not None else None
        tags = _loop_tags(key)

        copies.append((sample.path, dest, tags))

    if not dry_run:
        loops_dir.mkdir(parents=True, exist_ok=True)
        sidecar_items: dict[str, list[str]] = {}
        for src, dest, tags in copies:
            shutil.copy2(src, dest)
            sidecar_items[dest.name] = tags
        write_folder_info(loops_dir, sidecar_items)

    return len(loops)
