# ablekit

Convert Native Instruments Maschine expansions into Ableton Live drum racks.

Reconstructs the real named kits from each expansion (via NI's sample naming
convention) as Live 12 `.adg` drum racks — GM-style pad layout, hi-hat choke
groups, clean pad labels, tonal one-shots on the upper pads — and installs
them into the Ableton User Library. Construction loops are placed in a
separate, clearly-named folder so they're browsable and auto-warp-ready in
Live.

## Usage

    uv run ablekit                 # TUI: browse expansions, preview kits, convert
    uv run ablekit list            # show detected expansions
    uv run ablekit convert --all   # convert every detected expansion
    uv run ablekit convert "/Users/Shared/Polar Flare Library" --dry-run

Kits land in `User Library/Presets/Instruments/Drum Rack/Ablekit/`,
samples in `User Library/Samples/Imported/Ablekit/`.
In Live's browser: User Library → Presets → Instruments → Drum Rack → Ablekit.

## TUI keys

| Key | Action |
|---|---|
| `←` `→` | switch pane (expansions / kits) |
| `↑` `↓` | move cursor |
| `enter` | kit detail: pad layout preview (`esc` back) |
| `space` | select/deselect kit under cursor |
| `a` | select all kits in expansion |
| `c` | convert selected kits (or kit under cursor if none selected) |
| `d` | dry run — show what would be created, write nothing |
| `?` | help |
| `q` | quit |

Conversion runs in a progress modal showing each kit as it converts, the
final summary, and where the kits were written.

## Pad layout

GM-style mapping on notes 36–51 so standard MIDI drum patterns line up:

    48 TomHi  | 49 Crash  | 50 Crash2  | 51 Ride
    44 PedalHH| 45 TomMid | 46 OpenHH  | 47 Tom
    40 Snare2 | 41 TomLo  | 42 ClosedHH| 43 Tom
    36 Kick   | 37 Rim    | 38 Snare   | 39 Clap

Percussion and overflow fill the empty grid slots; tonal one-shots stack above
from note 52. Hi-hat pads share a choke group.

## Sample handling

Samples are **copied**, not linked. Every sample a kit uses is copied into
`User Library/Samples/Imported/Ablekit/<expansion>/<kit>/` and the `.adg`
references that copy — never the originals in `/Users/Shared`.

- Kits are self-contained: they survive uninstalling or moving the expansion
  in Native Access, and work with Live's "Collect All and Save".
- Disk cost is roughly the size of each expansion's matched samples
  (loops are the bulk of it). Only kit-matched files are copied, and each
  sample belongs to exactly one kit, so there is no cross-kit duplication.
- Re-running a conversion overwrites the copies in place (idempotent).

## Construction loops

Construction loops are **not** placed on the drum rack. Instead they are
copied to:

    User Library/Samples/Imported/Ablekit/<Expansion>/Loops/<Kit>/

and renamed to `<Kit> <Part> [<n>] [<Key>] <BPM>bpm.wav`
(e.g. `Akka Drums 3 115bpm.wav`, `Akka Full E 115bpm.wav`). The `<BPM>bpm`
suffix lets Live auto-warp the loop to the session tempo on drag-in.

Browse them in Live: User Library → Samples → Imported → Ablekit → \<Expansion\>
→ Loops → \<Kit\>.

Each loop is tagged `Type → Loop` (plus `Key` when a key is in the filename)
so they appear in Live's browser filters.

## Browser tags (Live 12)

Every converted kit and sample gets Live 12 browser tags written as XMP
sidecars (`Ableton Folder Info/dc66a3fa….xmp`), so kits and samples are
searchable and filterable in Live's browser:

- **Kits** are tagged `Drums → Drum Kit → Hybrid Kit` (appears under Drums
  category in the browser).
- **Samples** are tagged by role: kick → `Drums → Kick`, snare →
  `Drums → Snare → Snare Hit`, closed hi-hat → `Drums → Hihat → Closed Hihat`,
  etc. One-shots get `Type → One Shot`.
- **Loops** get `Type → Loop` and, when a key is detected in the filename,
  `Key → <note>` (plus `Key → Minor` for minor-mode loops). They live in their
  own `Loops/<Kit>/` folder — see Construction loops above.
- **Everything** gets `Creator → Native Instruments` (content author) and
  `Creator → Ablekit` (converter — one-click filter for all ablekit output).

## Notes

- `.mxgrp` kit binaries are never parsed; kit membership is recovered from
  sample filenames (tolerant of NI's real-world naming dirt: case mismatches,
  spaced forms, plural/digit suffixes, truncated and typo'd kit names).
- Mixer/FX/velocity settings inside Maschine kits are not converted.
- Expansions without the `Samples/Drums|One Shots|Loops` hierarchy (e.g.
  flat artist-folder packs like Community Drive) are detected but their kits
  are skipped — a category-fallback mode is a possible future addition.
- The summary line distinguishes two kinds of unassigned audio:
  **ignored** = `Samples/Instruments/` multisample sets (polyphonic key maps
  that don't fit one-sample-per-pad — excluded by design, not an error);
  **unmatched** = classifiable files that no kit token matched (usually NI
  naming errors in the wild). Only `unmatched` warrants attention.
  Unmatched files are listed by path (relative to `Samples/`) in the CLI
  output and by filename in the TUI convert modal.
- Misnamed sample files (NI typos) are fuzzy-matched to the closest kit when
  the match is unambiguous (SequenceMatcher ratio ≥ 0.84, margin ≥ 0.05 over
  second-best). Fuzzy-fixed files are listed in CLI output as `~ <path> -> <kit>`.
  Disable with `--no-fuzzy` if you prefer strict token matching only.
- ADG templates are generated from a drum rack saved in the developer's own
  copy of Live via `scripts/build_templates.py`. To regenerate (e.g. for a
  newer Live version), save a single-pad drum rack preset and run:
  `uv run python scripts/build_templates.py "/path/to/Drum Rack.adg"`

## Development

    uv sync
    uv run pytest          # 93 tests incl. real-data integration (needs Polar Flare installed)
