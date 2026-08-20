#!/usr/bin/env python3
"""Tests for Mark Editor 0.4.0."""

import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mark_editor import (
    APP_NAME,
    DEFAULT_THEME,
    RELEASE,
    THEMES,
    VERSION,
    MarkEditor,
    ensure_cache_dir,
    font_installed,
    load_theme,
    resolve_font,
    save_theme,
    tkfont_families,
)


class TestAppMetadata(unittest.TestCase):
    def test_app_name(self):
        self.assertEqual(APP_NAME, "Mark Editor")

    def test_version(self):
        self.assertEqual(VERSION, "0.4.0")

    def test_release(self):
        self.assertEqual(RELEASE, "2026.08")

    def test_themes(self):
        self.assertIn("bootstrap-light", THEMES)
        self.assertIn("bootstrap-dark", THEMES)
        self.assertEqual(DEFAULT_THEME, "bootstrap-light")


class TestFontUtils(unittest.TestCase):
    def setUp(self):
        try:
            import tkinter as tk

            self.root = tk.Tk()
            self.root.withdraw()
        except Exception:
            self.skipTest("Tkinter not available")

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()

    def test_font_families_list(self):
        families = tkfont_families()
        self.assertIsInstance(families, list)
        self.assertTrue(len(families) > 0)

    def test_font_installed_unknown(self):
        result = font_installed("__nonexistent_font_xyz__")
        self.assertFalse(result)

    def test_font_installed_system(self):
        result = font_installed("Courier")
        self.assertIsInstance(result, bool)

    def test_resolve_font_returns_string(self):
        family = resolve_font("sans")
        self.assertIsInstance(family, str)
        self.assertTrue(len(family) > 0)

    def test_resolve_font_categories(self):
        for category in ("sans", "serif", "mono"):
            family = resolve_font(category)
            self.assertIsInstance(family, str)
            self.assertTrue(len(family) > 0)


class TestThemeStorage(unittest.TestCase):
    def setUp(self):
        # Redirect config to a temp dir so the test never touches real config.
        import mark_editor as me

        self._orig_config = me.CONFIG_DIR
        self._orig_theme_file = me.THEME_FILE
        self._tmp = Path(tempfile.mkdtemp())
        me.CONFIG_DIR = self._tmp / ".config"
        me.THEME_FILE = me.CONFIG_DIR / "theme.json"

    def tearDown(self):
        import mark_editor as me

        me.CONFIG_DIR = self._orig_config
        me.THEME_FILE = self._orig_theme_file

    def test_save_and_load_theme(self):
        save_theme("one-dark")
        self.assertEqual(load_theme(), "one-dark")

    def test_load_default_when_missing(self):
        self.assertEqual(load_theme(), DEFAULT_THEME)


class TestCacheDir(unittest.TestCase):
    def test_ensure_cache_dir(self):
        import mark_editor as me

        orig = me.CACHE_DIR
        try:
            tmp = Path(tempfile.mkdtemp())
            me.CACHE_DIR = tmp / "mark_edit"
            path = ensure_cache_dir()
            self.assertTrue(path.exists())
            self.assertTrue(path.is_dir())
        finally:
            me.CACHE_DIR = orig


class TestEditor(unittest.TestCase):
    """Behavioural tests that instantiate the real application."""

    def setUp(self):
        try:
            self.app = MarkEditor()
            self.app.update_idletasks()
            self.app.update()
        except Exception:
            self.skipTest("Tkinter display not available")

    def tearDown(self):
        if hasattr(self, "app"):
            try:
                self.app.destroy()
            except Exception:
                pass

    def test_title(self):
        self.assertIn(APP_NAME, self.app.title())

    def test_heading(self):
        self.app._editor.insert("1.0", "text")
        self.app._editor.mark_set("insert", "1.0")
        self.app._on_heading(2)
        text = self.app._editor.get("1.0", "end-1c")
        self.assertTrue(text.startswith("## "))

    def test_paragraph(self):
        self.app._editor.insert("1.0", "## title")
        self.app._editor.mark_set("insert", "1.0")
        self.app._on_paragraph()
        text = self.app._editor.get("1.0", "end-1c")
        self.assertFalse(text.startswith("## "))

    def test_ordered_list(self):
        self.app._editor.insert("1.0", "item")
        self.app._editor.mark_set("insert", "1.0")
        self.app._on_ordered_list()
        text = self.app._editor.get("1.0", "end-1c")
        self.assertTrue(text.startswith("1. "))

    def test_unordered_list(self):
        self.app._editor.insert("1.0", "item")
        self.app._editor.mark_set("insert", "1.0")
        self.app._on_unordered_list()
        text = self.app._editor.get("1.0", "end-1c")
        self.assertTrue(text.startswith("* "))

    def test_blockquote(self):
        self.app._editor.insert("1.0", "quote")
        self.app._editor.mark_set("insert", "1.0")
        self.app._on_blockquote()
        text = self.app._editor.get("1.0", "end-1c")
        self.assertTrue(text.startswith("> "))

    def test_line_up(self):
        self.app._editor.insert("1.0", "A\nB\nC\n")
        self.app._editor.mark_set("insert", "2.0")
        self.app._on_line_up()
        text = self.app._editor.get("1.0", "end-1c")
        self.assertEqual(text, "B\nA\nC\n")

    def test_line_down(self):
        self.app._editor.insert("1.0", "A\nB\nC\n")
        self.app._editor.mark_set("insert", "1.0")
        self.app._on_line_down()
        text = self.app._editor.get("1.0", "end-1c")
        self.assertEqual(text, "B\nA\nC\n")

    def test_delete_line(self):
        self.app._editor.insert("1.0", "A\nB\nC\n")
        self.app._editor.mark_set("insert", "2.0")
        self.app._on_delete_line()
        text = self.app._editor.get("1.0", "end-1c")
        self.assertEqual(text, "A\nC\n")

    def test_wrap_selection(self):
        self.app._editor.insert("1.0", "word")
        self.app._editor.tag_add("sel", "1.0", "1.4")
        self.app._wrap_selection("**")
        text = self.app._editor.get("1.0", "end-1c")
        self.assertEqual(text, "**word**")

    def test_zoom_in_out(self):
        size = self.app.editor_font_size
        self.app._on_zoom_in()
        self.assertEqual(self.app.editor_font_size, size + 2)
        self.app._on_zoom_out()
        self.assertEqual(self.app.editor_font_size, size)

    def test_toggle_theme(self):
        current = self.app.style.theme_use()
        self.app._on_toggle_theme()
        self.assertNotEqual(self.app.style.theme_use(), current)

    def test_modified_flag(self):
        self.app._editor.insert("1.0", "x")
        self.app._editor.edit_modified(True)
        self.app._on_editor_modified()
        self.assertTrue(self.app.is_modified)

    def test_line_numbers(self):
        self.app._editor.insert("1.0", "a\nb\nc\n")
        self.app._update_line_numbers()
        numbers = self.app._line_numbers.get("1.0", "end-1c")
        self.assertEqual(numbers, "1\n2\n3\n4")

    def test_md_to_plain(self):
        text = self.app._md_to_plain("# Title\n\nSome **bold** and [link](https://x.com).")
        self.assertIn("Title", text)
        self.assertIn("Some bold and link.", text)

    def test_perform_convert_html(self):
        tmp = Path(tempfile.mkdtemp()) / "out.html"
        self.app._editor.insert("1.0", "# Hello")
        self.app._perform_convert(tmp, ".html")
        html = tmp.read_text(encoding="utf-8")
        self.assertIn("<h1>", html)

    def test_perform_convert_txt(self):
        tmp = Path(tempfile.mkdtemp()) / "out.txt"
        self.app._editor.insert("1.0", "# Hello")
        self.app._perform_convert(tmp, ".txt")
        txt = tmp.read_text(encoding="utf-8")
        self.assertIn("Hello", txt)

    def test_save_to(self):
        tmp = Path(tempfile.mkdtemp()) / "doc.md"
        self.app._editor.insert("1.0", "hello world")
        with unittest.mock.patch("mark_editor.Messagebox.show_info"):
            self.app._save_to(tmp)
        self.assertEqual(tmp.read_text(encoding="utf-8"), "hello world")
        self.assertFalse(self.app.is_modified)


class TestDialogs(unittest.TestCase):
    def _root(self):
        try:
            import ttkbootstrap as tb

            root = tb.Window()
            root.withdraw()
            return root
        except Exception:
            self.skipTest("Tkinter not available")

    def test_find_dialog_creation(self):
        import tkinter as tk

        from mark_editor import FindDialog

        root = self._root()
        text = tk.Text(root)
        dlg = FindDialog(root, text)
        self.assertIsNotNone(dlg)
        dlg.destroy()
        root.destroy()

    def test_replace_dialog_creation(self):
        import tkinter as tk

        from mark_editor import ReplaceDialog

        root = self._root()
        text = tk.Text(root)
        dlg = ReplaceDialog(root, text)
        self.assertIsNotNone(dlg)
        dlg.destroy()
        root.destroy()

    def test_table_dialog_creation(self):
        from mark_editor import TableDialog

        root = self._root()
        dlg = TableDialog(root)
        self.assertIsNotNone(dlg)
        dlg.destroy()
        root.destroy()

    def test_furigana_dialog_creation(self):
        from mark_editor import FuriganaDialog

        root = self._root()
        dlg = FuriganaDialog(root)
        self.assertIsNotNone(dlg)
        dlg.destroy()
        root.destroy()

    def test_header_link_dialog_creation(self):
        from mark_editor import HeaderLinkDialog

        root = self._root()
        dlg = HeaderLinkDialog(root)
        self.assertIsNotNone(dlg)
        dlg.destroy()
        root.destroy()

    def test_footnote_dialog_creation(self):
        from mark_editor import FootnoteDialog

        root = self._root()
        dlg = FootnoteDialog(root)
        self.assertIsNotNone(dlg)
        dlg.destroy()
        root.destroy()

    def test_definition_list_dialog_creation(self):
        from mark_editor import DefinitionListDialog

        root = self._root()
        dlg = DefinitionListDialog(root)
        self.assertIsNotNone(dlg)
        dlg.destroy()
        root.destroy()

    def test_yaml_dialog_creation(self):
        from mark_editor import YAMLFrontMatterDialog

        root = self._root()
        dlg = YAMLFrontMatterDialog(root)
        self.assertIsNotNone(dlg)
        dlg.destroy()
        root.destroy()

    def test_datetime_dialog_creation(self):
        from mark_editor import DateTimeDialog

        root = self._root()
        dlg = DateTimeDialog(root)
        self.assertIsNotNone(dlg)
        dlg.destroy()
        root.destroy()


class TestMarkdownConversion(unittest.TestCase):
    def test_converter_importable(self):
        from markdown2html5_base import MarkdownToHTML

        conv = MarkdownToHTML()
        html = conv.convert("# Title")
        self.assertIn("<h1>", html)


if __name__ == "__main__":
    unittest.main()
