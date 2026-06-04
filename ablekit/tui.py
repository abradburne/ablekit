from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.coordinate import Coordinate
from textual.screen import ModalScreen, Screen
from textual.widgets import DataTable, Footer, Header, Label, ListItem, ListView, ProgressBar, Static

from .convert import convert_expansion
from .installer import DEFAULT_USER_LIBRARY
from .layout import assign_pads
from .matcher import match_expansion
from .models import Expansion, Kit, Role
from .scanner import SHARED, discover


_HELP_TEXT = """\
ablekit — Maschine expansions → Ableton drum racks

Navigation                              Selection
  ←/→     switch pane                     space   select/deselect kit
  ↑/↓     move cursor                     a       select all kits
  enter   kit detail (esc back)
  tab     cycle focus                   Convert
                                          c       convert selected kits
Other                                             (cursor kit if none)
  ?       this help                       d       dry run (writes nothing)
  q       quit

Output — inside your User Library
  kits     Presets/Instruments/Drum Rack/Ablekit/<expansion>/
  samples  Samples/Imported/Ablekit/<expansion>/<kit>/
  loops    Samples/Imported/Ablekit/<expansion>/Loops/<kit>/
           renamed '<Kit> <Part> <n> <Key> <BPM>bpm.wav' → Live auto-warps

Find in Live's browser
  kits     User Library → Presets → Instruments → Drum Rack → Ablekit
  loops    User Library → Samples → Imported → Ablekit → <expansion> → Loops\
"""


class HelpScreen(ModalScreen):
    """Keyboard shortcut reference."""

    CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-panel {
        width: 84;
        max-width: 95%;
        height: auto;
        border: solid $accent;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id='help-panel'):
            yield Static(_HELP_TEXT, markup=False)

    def on_key(self, event) -> None:
        self.dismiss()


def kit_summary(kit: Kit) -> str:
    drums = sum(1 for s in kit.samples if s.role not in (Role.TONAL, Role.LOOP))
    tonal = sum(1 for s in kit.samples if s.role is Role.TONAL)
    loops = sum(1 for s in kit.samples if s.role is Role.LOOP)
    return f'{drums} drums, {tonal} tonal, {loops} loops'


class ConvertScreen(ModalScreen):
    """Progress modal for converting kits across one or more expansions."""

    CSS = """
    ConvertScreen {
        align: center middle;
    }
    #convert-panel {
        width: 80;
        height: auto;
        max-height: 90%;
        overflow-y: auto;
        border: solid $accent;
        padding: 1 2;
    }
    #convert-title {
        text-align: center;
        margin-bottom: 1;
    }
    #convert-log {
        margin-top: 1;
        height: auto;
    }
    #convert-summary {
        margin-top: 1;
        height: auto;
    }
    #convert-dest {
        margin-top: 1;
        height: auto;
    }
    #convert-hint {
        margin-top: 1;
        height: auto;
        color: $text-muted;
        text-align: center;
    }
    """

    def __init__(
        self,
        jobs: list[tuple[Expansion, list[str]]],
        user_library: Path,
        dry_run: bool,
    ) -> None:
        super().__init__()
        self.jobs = jobs
        self.user_library = user_library
        self.dry_run = dry_run
        self.done: bool = False

    def compose(self) -> ComposeResult:
        verb = 'Dry run' if self.dry_run else 'Converting'
        if len(self.jobs) == 1:
            title = f'{verb}: {self.jobs[0][0].name}'
        else:
            title = f'{verb}: {len(self.jobs)} expansions'
        total_kits = sum(len(kit_names) for _, kit_names in self.jobs)
        with Vertical(id='convert-panel'):
            yield Label(title, id='convert-title')
            yield ProgressBar(total=total_kits, show_eta=False, id='convert-progress')
            yield Label('', id='convert-log')
            yield Label('', id='convert-summary')
            yield Label('', id='convert-dest')
            yield Label('', id='convert-hint')

    def on_mount(self) -> None:
        self.run_worker(self._convert_worker, thread=True)

    def _convert_worker(self) -> None:
        def on_progress(kit_name: str) -> None:
            self.app.call_from_thread(self._advance, kit_name)

        # Aggregate results across all jobs.
        all_kits: list = []
        all_skipped: list[str] = []
        all_unmatched: list[Path] = []
        all_ignored: int = 0
        all_fuzzy: list = []

        for expansion, kit_names in self.jobs:
            result = convert_expansion(
                expansion,
                user_library=self.user_library,
                dry_run=self.dry_run,
                only_kits=set(kit_names),
                progress=on_progress,
            )
            all_kits.extend(result.kits)
            all_skipped.extend(result.skipped)
            all_unmatched.extend(result.unmatched)
            all_ignored += result.ignored
            all_fuzzy.extend(result.fuzzy)

        verb = 'would create' if self.dry_run else 'created'
        total_loops = sum(r.loops for r in all_kits)
        parts = [
            f'{verb} {len(all_kits)} kits ({total_loops} loops)',
            f'skipped {len(all_skipped)}',
        ]
        if all_unmatched:
            parts.append(f'unmatched {len(all_unmatched)}')
        if all_ignored:
            parts.append(f'ignored {all_ignored}')
        if all_fuzzy:
            parts.append(f'fuzzy {len(all_fuzzy)}')
        summary = ', '.join(parts)
        self.app.call_from_thread(self._finish, summary, all_unmatched)

    def _advance(self, kit_name: str) -> None:
        self.query_one('#convert-log', Label).update(kit_name)
        self.query_one('#convert-progress', ProgressBar).advance(1)

    def _finish(self, summary: str, unmatched: list[Path] | None = None) -> None:
        if unmatched:
            names = [p.name for p in unmatched[:5]]
            log_text = 'unmatched: ' + '\n'.join(names)
            if len(unmatched) > 5:
                log_text += f'\n+{len(unmatched) - 5} more'
            self.query_one('#convert-log', Label).update(log_text)
        else:
            self.query_one('#convert-log', Label).update('')
        self.query_one('#convert-summary', Label).update(summary)
        if self.dry_run:
            self.query_one('#convert-dest', Label).update('(dry run — nothing written)')
            self.query_one('#convert-hint', Label).update('press any key to close')
        elif len(self.jobs) == 1:
            expansion = self.jobs[0][0]
            kits_dest = (
                self.user_library
                / 'Presets'
                / 'Instruments'
                / 'Drum Rack'
                / 'Ablekit'
                / expansion.name
            )
            loops_dest = (
                self.user_library
                / 'Samples'
                / 'Imported'
                / 'Ablekit'
                / expansion.name
                / 'Loops'
            )
            self.query_one('#convert-dest', Label).update(
                f'kits  -> {kits_dest}\nloops -> {loops_dest}')
            self.query_one('#convert-hint', Label).update(
                'In Live: kits under Browser → User Library → Presets → Instruments'
                ' → Drum Rack → Ablekit; loops under Samples → Imported → Ablekit.'
                ' Press any key to close.'
            )
        else:
            kits_dest = (
                self.user_library / 'Presets' / 'Instruments' / 'Drum Rack' / 'Ablekit'
            )
            loops_dest = (
                self.user_library / 'Samples' / 'Imported' / 'Ablekit'
            )
            self.query_one('#convert-dest', Label).update(
                f'kits  -> {kits_dest}/\nloops -> {loops_dest}/')
            self.query_one('#convert-hint', Label).update(
                'In Live: kits under Browser → User Library → Presets → Instruments'
                ' → Drum Rack → Ablekit; loops under Samples → Imported → Ablekit.'
                ' Press any key to close.'
            )
        self.done = True

    def on_key(self, event) -> None:
        if self.done:
            self.dismiss(self.query_one('#convert-summary', Label).content)
        # While running, swallow all keys (no cancel support)


class KitDetailScreen(Screen):
    """Pad layout preview for one kit: note -> pad name -> file."""

    BINDINGS = [('escape', 'app.pop_screen', 'back')]

    def __init__(self, kit: Kit) -> None:
        super().__init__()
        self.kit = kit

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(f' {self.kit.name}', id='kit-title')
        table = DataTable()
        table.add_columns('note', 'pad', 'file')
        pads, dropped = assign_pads(self.kit.samples)
        for pad in pads:
            table.add_row(str(pad.note), pad.sample.pad_name, pad.sample.path.name)
        if dropped:
            table.add_row('—', f'{len(dropped)} dropped (>127)', '')
        yield table
        yield Footer()


class AblekitApp(App):
    TITLE = 'ablekit'
    CSS = """
    #expansions { width: 40%; border: solid $accent; }
    #kits { border: solid $accent; }
    #status { dock: bottom; height: 1; padding: 0 1; }
    """
    BINDINGS = [
        Binding('right', 'focus_kits', 'focus kits', priority=True, show=False),
        Binding('left', 'focus_expansions', 'focus expansions', priority=True, show=False),
        ('space', 'toggle_kit', 'select'),
        ('a', 'select_all', 'select all'),
        ('c', 'convert', 'convert'),
        ('d', 'dry_run', 'dry run'),
        Binding('question_mark', 'help', 'help'),
        Binding('h', 'help', 'help', show=False),
        ('q', 'quit', 'quit'),
    ]

    def __init__(self, root: Path = SHARED,
                 user_library: Path = DEFAULT_USER_LIBRARY) -> None:
        super().__init__()
        self.root = root
        self.user_library = user_library
        self.expansions: list[Expansion] = []
        self.kits: list[Kit] = []
        self._selections: dict[str, set[str]] = {}  # expansion name → selected kit names
        self.current: Expansion | None = None

    @property
    def selected(self) -> set[str]:
        """Return the live selection set for the current expansion."""
        if self.current is None:
            return set()
        return self._selections.setdefault(self.current.name, set())

    @selected.setter
    def selected(self, value: set[str]) -> None:
        """Assign a new selection set for the current expansion."""
        if self.current is None:
            return
        self._selections[self.current.name] = value

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield ListView(id='expansions')
            yield DataTable(id='kits')
        yield Label('ready', id='status')
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one('#kits', DataTable)
        table.add_columns('sel', 'kit', 'contents')
        table.cursor_type = 'row'
        self.expansions = discover(self.root)
        lv = self.query_one('#expansions', ListView)
        for exp in self.expansions:
            lv.append(ListItem(Label(f'{exp.name} ({len(exp.kit_names)} kits)')))
        if self.expansions:
            lv.index = 0
            self.show_expansion(self.expansions[0])

    def show_expansion(self, exp: Expansion) -> None:
        self.current = exp
        self.kits, _, _ignored, _fuzzy = match_expansion(exp)
        self.refresh_kit_table()
        n = len(self.selected)
        if n:
            status = f'{n} kit{"s" if n != 1 else ""} selected'
            self.query_one('#status', Label).update(status)

    def refresh_kit_table(self) -> None:
        table = self.query_one('#kits', DataTable)
        table.clear()
        for kit in self.kits:
            mark = 'x' if kit.name in self.selected else ' '
            table.add_row(mark, kit.name, kit_summary(kit), key=kit.name)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        idx = self.query_one('#expansions', ListView).index
        if idx is not None and 0 <= idx < len(self.expansions):
            if self.expansions[idx] is not self.current:
                self.show_expansion(self.expansions[idx])

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        kit = next((k for k in self.kits if k.name == event.row_key.value), None)
        if kit:
            self.push_screen(KitDetailScreen(kit))

    def action_focus_kits(self) -> None:
        """Move focus from the expansion list to the kit table (right arrow)."""
        if self.focused is self.query_one('#expansions'):
            self.query_one('#kits').focus()

    def action_focus_expansions(self) -> None:
        """Move focus from the kit table to the expansion list (left arrow)."""
        if self.focused is self.query_one('#kits'):
            self.query_one('#expansions').focus()

    def _cursor_kit(self) -> Kit | None:
        table = self.query_one('#kits', DataTable)
        if table.row_count == 0:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return next((k for k in self.kits if k.name == row_key.value), None)

    def action_toggle_kit(self) -> None:
        table = self.query_one('#kits', DataTable)
        # Only toggle when the kit table itself has focus — pressing space on
        # the expansion list would silently toggle the cursor row of the table.
        if self.focused is not table:
            return
        kit = self._cursor_kit()
        if kit is None:
            return
        if kit.name in self.selected:
            self.selected.discard(kit.name)
        else:
            self.selected.add(kit.name)
        # Update only the 'sel' cell in-place so the cursor row doesn't reset.
        mark = 'x' if kit.name in self.selected else ' '
        table.update_cell_at(Coordinate(table.cursor_row, 0), mark)
        n = len(self.selected)
        status = f'{n} kit{"s" if n != 1 else ""} selected'
        self.query_one('#status', Label).update(status)

    def action_select_all(self) -> None:
        self.selected = {k.name for k in self.kits}
        # Preserve cursor position across the full table rebuild.
        table = self.query_one('#kits', DataTable)
        saved_row = table.cursor_row
        self.refresh_kit_table()
        if table.row_count > 0:
            table.move_cursor(row=min(saved_row, table.row_count - 1))
        n = len(self.selected)
        status = f'{n} kit{"s" if n != 1 else ""} selected'
        self.query_one('#status', Label).update(status)

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_convert(self) -> None:
        self._run_convert(dry_run=False)

    def action_dry_run(self) -> None:
        self._run_convert(dry_run=True)

    def _run_convert(self, dry_run: bool) -> None:
        if self.current is None:
            self.query_one('#status', Label).update('nothing to convert')
            return

        # Gather selections across ALL expansions (intersect with actual kit names
        # for safety against stale entries).
        exp_by_name = {exp.name: exp for exp in self.expansions}
        jobs: list[tuple[Expansion, list[str]]] = []
        converted_exp_names: list[str] = []
        for exp_name, sel_set in self._selections.items():
            if not sel_set:
                continue
            exp = exp_by_name.get(exp_name)
            if exp is None:
                continue
            valid_names = sorted(sel_set & set(exp.kit_names))
            if valid_names:
                jobs.append((exp, valid_names))
                converted_exp_names.append(exp_name)

        table = self.query_one('#kits', DataTable)
        if not jobs:
            if self.focused is table:
                # No explicit selection: convert only the kit under the cursor.
                kit = self._cursor_kit()
                if kit and kit.samples:
                    jobs = [(self.current, [kit.name])]
            else:
                # Kits table is not focused and nothing is selected — guide the user.
                self.query_one('#status', Label).update(
                    'no kits selected — space to select, a for all'
                )
                return

        if not jobs:
            self.query_one('#status', Label).update('nothing to convert')
            return

        def on_dismiss(summary: str | None) -> None:
            # Clear selections for all converted expansions and refresh the table.
            for exp_name in converted_exp_names:
                if exp_name in self._selections:
                    self._selections[exp_name].clear()
            self.refresh_kit_table()
            self.query_one('#status', Label).update(summary or 'ready')

        screen = ConvertScreen(jobs, self.user_library, dry_run)
        self.push_screen(screen, on_dismiss)


if __name__ == '__main__':
    AblekitApp().run()
