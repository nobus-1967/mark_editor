#!/usr/bin/env python3
"""Tests for Mark Editor 0.9.0 (GTK4)."""

import os
import sys
import tempfile
import unittest
import unittest.mock
from contextlib import suppress
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mark_editor.constants import (
    APP_NAME,
    DEFAULT_THEME,
    RELEASE,
    THEMES,
    VERSION,
)
from mark_editor.helpers import (
    cleanup_temp_html,
    cleanup_temp_md,
    ensure_cache_dir,
    get_converter,
    load_font,
    load_theme,
    md_to_html,
    md_to_plain,
    save_font,
    save_theme,
)


class _IsolatedConfigMixin:
    """Point mark_editor's config and cache dirs at a temporary directory."""

    def setUp(self):
        """Redirect config and cache dirs to a fresh temporary directory."""
        import mark_editor.helpers as mh

        self._orig = (mh.CONFIG_DIR, mh.THEME_FILE, mh.CACHE_DIR)
        self._tmp = Path(tempfile.mkdtemp())
        mh.CONFIG_DIR = self._tmp / ".config"
        mh.THEME_FILE = mh.CONFIG_DIR / "theme.json"
        mh.CACHE_DIR = self._tmp / ".cache"

    def tearDown(self):
        """Restore the original config and cache dirs."""
        import mark_editor.helpers as mh

        mh.CONFIG_DIR, mh.THEME_FILE, mh.CACHE_DIR = self._orig


class TestAppMetadata(unittest.TestCase):
    """Check the application's static metadata constants."""

    def test_app_name(self):
        """APP_NAME is 'Mark Editor'."""
        self.assertEqual(APP_NAME, "Mark Editor")

    def test_version(self):
        """VERSION matches the current release."""
        self.assertEqual(VERSION, "0.9.0")

    def test_release(self):
        """RELEASE is auto-derived as the current year.month."""
        from datetime import datetime

        self.assertEqual(RELEASE, datetime.now().strftime("%Y.%m"))

    def test_themes(self):
        """Both light and dark themes are available, light is the default."""
        self.assertIn("light", THEMES)
        self.assertIn("dark", THEMES)
        self.assertEqual(DEFAULT_THEME, "light")


class TestFontStorage(_IsolatedConfigMixin, unittest.TestCase):
    """Verify the editor font family and size persistence."""

    def test_default_font(self):
        """The default editor font is Noto Sans Mono at size 16."""
        self.assertEqual(load_font(), ("Noto Sans Mono", 16))

    def test_save_and_load_font(self):
        """Saved font settings round-trip through theme.json."""
        save_font("Monospace", 18)
        self.assertEqual(load_font(), ("Monospace", 18))


class TestThemeStorage(_IsolatedConfigMixin, unittest.TestCase):
    """Verify the light/dark theme persistence."""

    def test_save_and_load_theme(self):
        """Saved theme mode round-trips through theme.json."""
        save_theme("dark")
        self.assertEqual(load_theme(), "dark")

    def test_load_default_when_missing(self):
        """A missing theme file yields the default (light) theme."""
        self.assertEqual(load_theme(), DEFAULT_THEME)


class TestCacheDir(_IsolatedConfigMixin, unittest.TestCase):
    """Verify the cache directory helper."""

    def test_ensure_cache_dir(self):
        """ensure_cache_dir creates the cache directory."""
        path = ensure_cache_dir()
        self.assertTrue(path.exists())
        self.assertTrue(path.is_dir())


class TestEditor(_IsolatedConfigMixin, unittest.TestCase):
    """Behavioral tests that instantiate the real GTK4 application."""

    def setUp(self):
        """Isolate config dirs, then instantiate the GTK4 app window."""
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("GtkSource", "5")

        super().setUp()
        try:
            from gi.repository import Adw, GLib

            self._app = Adw.Application(application_id="com.github.mark_editor.test")
            self._app.register()
            from mark_editor.window import MarkEditorWindow

            self.app = MarkEditorWindow(application=self._app)
            self.app.present()
            GLib.idle_add(lambda: None)
        except Exception:
            self.skipTest("GTK4 display not available")

    def tearDown(self):
        """Close the window and restore config dirs."""
        if hasattr(self, "app"):
            with suppress(Exception):
                self.app.close()
        super().tearDown()

    def test_title(self):
        """The window title contains the application name."""
        self.assertIn(APP_NAME, self.app.get_title())

    def test_heading(self):
        """Applying a heading level prefixes the line with ## ."""
        self.app._editor.set_text("text")
        self.app._on_heading(2)
        self.assertTrue(self.app._editor.get_text().startswith("## "))

    def test_paragraph(self):
        """Applying a paragraph removes the heading marker."""
        self.app._editor.set_text("## title")
        self.app._on_paragraph()
        self.assertFalse(self.app._editor.get_text().startswith("## "))

    def test_ordered_list(self):
        """Applying an ordered list prefixes the line with '1. '."""
        self.app._editor.set_text("item")
        with unittest.mock.patch(
            "mark_editor.window.OrderedListDialog",
            return_value=unittest.mock.MagicMock(),
        ) as mock_dlg:
            self.app._on_ordered_list()
            callback = mock_dlg.call_args.args[0]
            callback(1)
        self.assertTrue(self.app._editor.get_text().startswith("1. "))

    def test_unordered_list(self):
        """Applying an unordered list prefixes the line with '- '."""
        self.app._editor.set_text("item")
        self.app._on_unordered_list()
        self.assertTrue(self.app._editor.get_text().startswith("- "))

    def test_todo_list(self):
        """Todo List adds/updates the [ ]/[x] marker on list items only."""
        cases = (
            ("- task", False, "- [ ] task"),
            ("- task", True, "- [x] task"),
            ("* task", False, "* [ ] task"),
            ("1. task", False, "1. [ ] task"),
            ("- [ ] task", True, "- [x] task"),
            ("1. [x] task", False, "1. [ ] task"),
            ("[x] task", False, "[ ] task"),
            ("task", False, "task"),
        )
        for text, checked, expected in cases:
            self.app._editor.set_text(text)
            with unittest.mock.patch(
                "mark_editor.window.TodoListDialog",
                return_value=unittest.mock.MagicMock(),
            ) as mock_dlg:
                self.app._on_todo_list()
                callback = mock_dlg.call_args.args[0]
                callback(checked)
            self.assertEqual(self.app._editor.get_text(), expected, msg=(text, checked))

    def test_blockquote(self):
        """Applying a blockquote prefixes the line with '> '."""
        self.app._editor.set_text("quote")
        self.app._on_blockquote()
        self.assertTrue(self.app._editor.get_text().startswith("> "))

    def test_code_block_selection(self):
        """Code Block fences a selection, otherwise wraps the current line."""
        self.app._editor.set_text("code: x = 1")
        self.app._editor.select_all()
        with unittest.mock.patch(
            "mark_editor.window.ask_string",
            return_value=None,
        ) as mock_ask:
            self.app._on_code_block()
            callback = mock_ask.call_args.args[3]
            callback("python")
        self.assertEqual(self.app._editor.get_text(), "```python\ncode: x = 1\n```")

        self.app._editor.set_text("plain text")
        with unittest.mock.patch(
            "mark_editor.window.ask_string",
            return_value=None,
        ) as mock_ask:
            self.app._on_code_block()
            callback = mock_ask.call_args.args[3]
            callback("")
        self.assertEqual(self.app._editor.get_text(), "```\nplain text\n```")

    def test_wrap_selection(self):
        """Wrapping a selection surrounds it with the given marker."""
        self.app._editor.set_text("word")
        self.app._editor.select_all()
        self.app._wrap_selection("**")
        self.assertEqual(self.app._editor.get_text(), "**word**")

    def test_table(self):
        """Applying a table-row insert puts a pipe row on the next line."""
        self.app._editor.set_text("Header")
        with unittest.mock.patch(
            "mark_editor.window.TableRowDialog",
            return_value=unittest.mock.MagicMock(),
        ) as mock_dlg:
            self.app._on_add_table_row()
            callback = mock_dlg.call_args.args[0]
            callback(3)
        self.assertEqual(self.app._editor.get_text(), "Header\n| Cell | Cell | Cell |")

    def test_table_dialog_spins(self):
        """Table dialog spin buttons are usable and build the expected pattern."""
        from mark_editor.dialogs import TableDialog

        callback = unittest.mock.MagicMock()
        dlg = TableDialog(callback)
        self.assertEqual(dlg._cols_spin.get_adjustment().get_step_increment(), 1)
        self.assertEqual(dlg._rows_spin.get_adjustment().get_step_increment(), 1)
        self.assertGreater(dlg._cols_spin.get_climb_rate(), 0)
        dlg._cols_spin.set_value(3)
        dlg._rows_spin.set_value(3)
        dlg._on_insert()
        text = callback.call_args.args[0]
        self.assertIn("| Header | Header | Header |", text)
        self.assertIn("| :---: | :---: | :---: |", text)
        self.assertEqual(text.count("| Cell | Cell | Cell |"), 3)
        self.assertIn("| Footer | Footer | Footer |", text)

    def test_table_align(self):
        """Alignment markers insert at the cursor or replace a selection."""
        self.app._on_table_align(":---")
        self.assertEqual(self.app._editor.get_text(), ":---")
        self.app._editor.set_text("old")
        self.app._editor.select_all()
        self.app._on_table_align(":---:")
        self.assertEqual(self.app._editor.get_text(), ":---:")

    def test_balance_table(self):
        """Balance Table pads every row to equal column widths."""
        table = (
            "| Name       | Age |\n"
            "| :---       | :---: |\n"
            "| Alice      | 30 |\n"
            "| Bob        | 25 |"
        )
        self.app._editor.set_text(table)
        _, cursor = self.app._editor.get_buffer().get_iter_at_line(2)
        self.app._editor.get_buffer().place_cursor(cursor)
        self.app._on_balance_table()
        expected = (
            "| Name  | Age   |\n"
            "| :---  | :---: |\n"
            "| Alice | 30    |\n"
            "| Bob   | 25    |\n"
        )
        self.assertEqual(self.app._editor.get_text(), expected)
        self.assertEqual(
            len(self.app._editor.get_line_text(1).split("|")),
            len(self.app._editor.get_line_text(4).split("|")),
        )

    def test_format_table_block(self):
        """The table block formatter pads columns and aligns the right border."""
        from mark_editor.window import _format_table_block

        lines = ["| a | bbb |", "| :--- | :---: |", "| x | y |"]
        formatted = _format_table_block(lines)
        self.assertEqual(
            formatted,
            ["| a   | bbb |", "| :--- | :---: |", "| x   | y   |"],
        )
        widths = {len(line) for line in formatted}
        self.assertEqual(widths, {len(formatted[0])})

    def test_zoom_in_out(self):
        """Zoom in increases the font size, zoom out restores it."""
        size = self.app.editor_font_size
        self.app._on_zoom_in()
        self.assertEqual(self.app.editor_font_size, size + 2)
        self.app._on_zoom_out()
        self.assertEqual(self.app.editor_font_size, size)

    def test_toggle_theme(self):
        """Theme toggle switches between light and dark modes."""
        start = load_theme()
        expected = "dark" if start == "light" else "light"
        self.app._on_toggle_theme()
        self.assertEqual(load_theme(), expected)

    def test_md_to_plain(self):
        """md_to_plain strips Markdown markup and keeps the text."""
        text = md_to_plain("# Title\n\nSome **bold** and [link](https://x.com).")
        self.assertIn("Title", text)
        self.assertIn("Some bold and link.", text)

    def test_md_to_plain_table(self):
        """md_to_plain keeps footer separators and normalizes alignment rows."""
        source = (
            "| Name | Qty | Price |\n"
            "| :--- | :---: | ---: |\n"
            "| A | 1 | 10.0 |\n"
            "| === | === | === |\n"
            "| Total | 1 | 10.0 |"
        )
        text = md_to_plain(source)
        self.assertIn("| === | === | === |", text)
        self.assertIn("| --- | --- | --- |", text)
        self.assertIn("| Total | 1 | 10.0 |", text)

    def test_md_to_html_convert(self):
        """md_to_html produces HTML5 heading markup."""
        self.app._editor.set_text("# Hello")
        html = md_to_html(self.app._editor.get_text())
        self.assertIn("<h1>", html)

    def test_md_to_plain_convert(self):
        """md_to_plain converts Markdown to readable text."""
        self.app._editor.set_text("# Hello")
        txt = md_to_plain(self.app._editor.get_text())
        self.assertIn("Hello", txt)

    def test_editor_text_roundtrip(self):
        """Editor text writes to a file and reads back unchanged."""
        tmp = Path(tempfile.mkdtemp()) / "doc.md"
        self.app._editor.set_text("hello world")
        tmp.write_text(self.app._editor.get_text(), encoding="utf-8")
        self.assertEqual(tmp.read_text(encoding="utf-8"), "hello world")

    def test_quick_view_without_css(self):
        """Quick view renders HTML5 output without embedded CSS."""
        self.app._editor.set_text("# Hello")
        with unittest.mock.patch(
            "mark_editor.window.QuickViewWindow",
            return_value=unittest.mock.MagicMock(),
        ) as mock_view:
            self.app._on_quick_view()
        html = (ensure_cache_dir() / "Temp.html").read_text(encoding="utf-8")
        self.assertIn("<h1>", html)
        self.assertNotIn("<style>", html)
        self.assertEqual(
            mock_view.call_args.kwargs["html_path"], ensure_cache_dir() / "Temp.html"
        )

    def test_quick_view_with_css(self):
        """Quick view with CSS renders HTML5 output with embedded styles."""
        self.app._editor.set_text("# Hello")
        with unittest.mock.patch(
            "mark_editor.window.QuickViewWindow",
            return_value=unittest.mock.MagicMock(),
        ) as mock_view:
            self.app._on_quick_view_css()
        html = (ensure_cache_dir() / "Temp.html").read_text(encoding="utf-8")
        self.assertIn("<h1>", html)
        self.assertIn("<style>", html)
        self.assertEqual(
            mock_view.call_args.kwargs["html_path"], ensure_cache_dir() / "Temp.html"
        )


class TestTempFileCleanup(unittest.TestCase):
    """Verify targeted deletion of temporary ~*.md and ~*.html files."""

    def _make_dir(self) -> Path:
        """Create a temp directory with mixed tilde and plain files."""
        d = Path(tempfile.mkdtemp())
        (d / "~doc.md").write_text("x", encoding="utf-8")
        (d / "~doc.html").write_text("x", encoding="utf-8")
        (d / "~notes").write_text("x", encoding="utf-8")
        (d / "doc.md").write_text("x", encoding="utf-8")
        return d

    def test_cleanup_temp_md_only(self):
        """cleanup_temp_md removes ~*.md but keeps other files."""
        d = self._make_dir()
        cleanup_temp_md(d)
        self.assertFalse((d / "~doc.md").exists())
        self.assertTrue((d / "~doc.html").exists())
        self.assertTrue((d / "~notes").exists())
        self.assertTrue((d / "doc.md").exists())

    def test_cleanup_temp_html_only(self):
        """cleanup_temp_html removes ~*.html but keeps other files."""
        d = self._make_dir()
        cleanup_temp_html(d)
        self.assertFalse((d / "~doc.html").exists())
        self.assertTrue((d / "~doc.md").exists())
        self.assertTrue((d / "~notes").exists())


class TestMarkdownConversion(unittest.TestCase):
    """Verify the Markdown converter is importable and functional."""

    def test_converter_importable(self):
        """get_converter returns a converter that emits HTML5 heading markup."""
        html = get_converter().convert("# Title")
        self.assertIn("<h1>", html)


if __name__ == "__main__":
    unittest.main()
