from pathlib import Path

from ablekit.tui import AblekitApp


async def test_tui_tab_moves_focus_to_kit_table(fake_expansion: Path):
    app = AblekitApp(root=fake_expansion.parent)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('tab')
        await pilot.pause()
        assert app.focused is app.query_one('#kits')


async def test_tui_right_arrow_focuses_kit_table(fake_expansion: Path):
    app = AblekitApp(root=fake_expansion.parent)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('right')
        await pilot.pause()
        assert app.focused is app.query_one('#kits')


async def test_tui_left_arrow_returns_to_expansion_list(fake_expansion: Path):
    app = AblekitApp(root=fake_expansion.parent)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('tab')   # focus kits
        await pilot.pause()
        await pilot.press('left')  # back to expansions
        await pilot.pause()
        assert app.focused is app.query_one('#expansions')


async def test_tui_lists_expansions_and_kits(fake_expansion: Path):
    app = AblekitApp(root=fake_expansion.parent)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.expansions
        assert app.expansions[0].name == 'Test Library'
        table = app.query_one('#kits')
        assert table.row_count == 2


async def test_tui_select_all_and_status(fake_expansion: Path):
    app = AblekitApp(root=fake_expansion.parent)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('a')
        assert len(app.selected) == 2


async def test_tui_toggle_keeps_cursor_row(fake_expansion: Path):
    app = AblekitApp(root=fake_expansion.parent)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('right')          # focus kit table
        await pilot.press('down')           # move to row 1
        table = app.query_one('#kits')
        assert table.cursor_row == 1
        await pilot.press('space')          # toggle selection
        assert table.cursor_row == 1        # cursor must NOT reset
        assert len(app.selected) == 1
        from textual.coordinate import Coordinate
        assert table.get_cell_at(Coordinate(1, 0)) == 'x'


async def test_tui_select_all_keeps_cursor_row(fake_expansion: Path):
    app = AblekitApp(root=fake_expansion.parent)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('right')          # focus kit table
        await pilot.press('down')           # move to row 1
        table = app.query_one('#kits')
        assert table.cursor_row == 1
        await pilot.press('a')              # select all
        assert table.cursor_row == 1        # cursor must NOT reset
        assert len(app.selected) == 2


async def test_tui_dry_run_convert_shows_unmatched(fake_expansion: Path, tmp_path: Path):
    from ablekit.tui import ConvertScreen
    lib = tmp_path / 'lib'
    app = AblekitApp(root=fake_expansion.parent, user_library=lib)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('a')
        await pilot.press('d')          # dry run → modal pushed
        await pilot.pause()
        assert isinstance(app.screen, ConvertScreen)
        for _ in range(60):
            await pilot.pause(0.05)
            if app.screen.done:
                break
        assert app.screen.done
        # #convert-log should show unmatched filenames after conversion done
        log = app.screen.query_one('#convert-log')
        assert 'Shaker Orphan 1.wav' in str(log.content)


async def test_tui_dry_run_convert(fake_expansion: Path, tmp_path: Path):
    from ablekit.tui import ConvertScreen
    lib = tmp_path / 'lib'
    app = AblekitApp(root=fake_expansion.parent, user_library=lib)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('a')
        await pilot.press('d')          # dry run → modal pushed
        await pilot.pause()
        # modal should now be active
        assert isinstance(app.screen, ConvertScreen)
        # wait for worker to complete (up to 3s)
        for _ in range(60):
            await pilot.pause(0.05)
            if app.screen.done:
                break
        assert app.screen.done
        # library must not have been written (dry run)
        assert not lib.exists()
        # summary label inside modal must say 'would create'
        summary = app.screen.query_one('#convert-summary')
        assert 'would create' in str(summary.content)
        # dismiss with any key → modal gone, status updated
        await pilot.press('enter')
        assert not isinstance(app.screen, ConvertScreen)
        status = app.query_one('#status')
        assert 'would create' in str(status.content)


async def test_tui_convert_shows_modal_and_writes(fake_expansion: Path, tmp_path: Path):
    # Under the new rules, 'c' with no selection and no kit-table focus shows a
    # status message instead of a modal. Focus the kits table first so the cursor
    # kit (row 0 = 'About Us Kit') converts when no selection is present.
    from ablekit.tui import ConvertScreen
    lib = tmp_path / 'lib'
    app = AblekitApp(root=fake_expansion.parent, user_library=lib)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('right')  # focus kits table; cursor stays on row 0
        await pilot.press('c')
        # modal pushed
        assert isinstance(app.screen, ConvertScreen)
        # wait for worker completion
        for _ in range(60):
            await pilot.pause(0.05)
            if app.screen.done:
                break
        assert app.screen.done
        # cursor was on row 0 = 'About Us Kit'; only that kit should be written
        assert (lib / 'Presets/Instruments/Drum Rack/Ablekit/Test Library/About Us Kit.adg').exists()
        await pilot.press('enter')
        assert not isinstance(app.screen, ConvertScreen)


async def test_tui_space_on_expansion_list_does_not_toggle(fake_expansion: Path):
    app = AblekitApp(root=fake_expansion.parent)
    async with app.run_test() as pilot:
        await pilot.pause()
        # focus is on expansion list at mount
        await pilot.press('space')
        assert app.selected == set()        # FAILS today: row-0 kit gets toggled


async def test_tui_convert_with_no_selection_converts_cursor_kit_only(fake_expansion: Path, tmp_path: Path):
    lib = tmp_path / 'lib'
    app = AblekitApp(root=fake_expansion.parent, user_library=lib)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('right')          # focus kits
        await pilot.press('down')           # cursor on second kit ('Akka Kit' — table order is About Us Kit, Akka Kit)
        await pilot.press('c')
        from ablekit.tui import ConvertScreen
        assert isinstance(app.screen, ConvertScreen)
        for _ in range(60):
            await pilot.pause(0.05)
            if app.screen.done:
                break
        await pilot.press('enter')
        adg_dir = lib / 'Presets/Instruments/Drum Rack/Ablekit/Test Library'
        assert sorted(p.name for p in adg_dir.glob('*.adg')) == ['Akka Kit.adg']  # FAILS today: both kits


async def test_tui_convert_selected_kits_only(fake_expansion: Path, tmp_path: Path):
    lib = tmp_path / 'lib'
    app = AblekitApp(root=fake_expansion.parent, user_library=lib)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('right')
        await pilot.press('space')          # select first kit (About Us Kit)
        assert len(app.selected) == 1
        await pilot.press('c')
        from ablekit.tui import ConvertScreen
        for _ in range(60):
            await pilot.pause(0.05)
            if app.screen.done:
                break
        await pilot.press('enter')
        adg_dir = lib / 'Presets/Instruments/Drum Rack/Ablekit/Test Library'
        assert sorted(p.name for p in adg_dir.glob('*.adg')) == ['About Us Kit.adg']


async def test_tui_help_screen_opens_and_closes(fake_expansion: Path):
    app = AblekitApp(root=fake_expansion.parent)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('question_mark')
        from ablekit.tui import HelpScreen
        assert isinstance(app.screen, HelpScreen)
        await pilot.press('escape')
        assert not isinstance(app.screen, HelpScreen)


async def test_tui_convert_shows_destination(fake_expansion: Path, tmp_path: Path):
    lib = tmp_path / 'lib'
    app = AblekitApp(root=fake_expansion.parent, user_library=lib)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('right')
        await pilot.press('a')
        await pilot.press('c')
        for _ in range(60):
            await pilot.pause(0.05)
            if app.screen.done:
                break
        dest = app.screen.query_one('#convert-dest')
        assert 'Drum Rack/Ablekit/Test Library' in str(dest.content)
