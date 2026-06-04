from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .convert import convert_expansion
from .installer import DEFAULT_USER_LIBRARY
from .scanner import SHARED, discover, scan_expansion


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='ablekit',
        description='Convert Maschine expansions into Ableton Live drum racks')
    sub = parser.add_subparsers(dest='command')

    list_p = sub.add_parser('list', help='show detected expansions')
    list_p.add_argument('--root', type=Path, default=SHARED)

    conv = sub.add_parser('convert', help='convert expansions to drum racks')
    conv.add_argument('paths', nargs='*', type=Path, help='expansion folders')
    conv.add_argument('--all', action='store_true', help='convert all detected expansions')
    conv.add_argument('--root', type=Path, default=SHARED,
                      help='where --all scans for expansions')
    conv.add_argument('--dry-run', action='store_true', help='print plan, write nothing')
    conv.add_argument('--user-library', type=Path, default=DEFAULT_USER_LIBRARY)

    args = parser.parse_args(argv)

    if args.command is None:
        from .tui import AblekitApp  # deferred: keep CLI startup instant
        AblekitApp().run()
        return 0

    if args.command == 'list':
        for exp in discover(args.root):
            print(f'{exp.name} — {len(exp.kit_names)} kits ({exp.path})')
        return 0

    expansions = list(discover(args.root)) if args.all else []
    for path in args.paths:
        exp = scan_expansion(path)
        if exp is None:
            print(f'not a Maschine expansion: {path}', file=sys.stderr)
            return 1
        expansions.append(exp)
    if not expansions:
        print('nothing to convert — pass expansion paths or --all', file=sys.stderr)
        return 1

    for exp in expansions:
        result = convert_expansion(
            exp, args.user_library, dry_run=args.dry_run,
            progress=lambda kit: print(f'  + {kit}'))
        verb = 'would create' if args.dry_run else 'created'
        total_loops = sum(r.loops for r in result.kits)
        summary = (f'{exp.name}: {verb} {len(result.kits)} kits ({total_loops} loops), '
                   f'skipped {len(result.skipped)}, unmatched {len(result.unmatched)}')
        if result.ignored:
            summary += f', ignored {result.ignored} (multisample instruments)'
        print(summary)
        if result.unmatched:
            samples_dir = exp.path / 'Samples'
            print('  unmatched (NI naming quirks, not converted):')
            for path in result.unmatched[:20]:
                try:
                    rel = path.relative_to(samples_dir)
                except ValueError:
                    rel = path
                print(f'  ! {rel}')
            if len(result.unmatched) > 20:
                print(f'  ... and {len(result.unmatched) - 20} more')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
