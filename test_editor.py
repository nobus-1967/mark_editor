#!/usr/bin/env python3
"""Tests for Mark Editor 0.6.0 (GTK4)."""

import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mark_editor.constants import (
    APP_NAME,
    CJK_CODES,
    DEFAULT_THEME,
    FONT_FAMILIES,
    RELEASE,
    TEMP_HTML,
    THEMES,
    VERSION,
)
from mark_editor.helpers import ensure_cache_dir, load_theme, save_theme, md_to_plain


class TestAppMetadata(unittest.TestCase):
    def test_app_name(self):
        self.assertEqual(APP_NAME, "Mark Editor")

    def test_version(self):
        self.assertEqual(VERSION, "0.6.0")

    def test_release(self):
        self.assertEqual(RELEASE, "2026.08")

    def test_themes(self):
        self.assertIn("light", THEMES)
        self.assertIn("dark", THEMES)
        self.assertEqual(DEFAULT_THEME, "light")


class TestFontFamilies(unittest.TestCase):
    def test_categories_present(self):
        for category in ("sans", "mono", "symbola"):
            self.assertIn(category, FONT_FAMILIES)

    def test_system_font_for_interface(self):
        self.assertEqual(FONT_FAMILIES["sans"], "")

    def test_mono_editor_font(self):
        self.assertEqual(FONT_FAMILIES["mono"], "Noto Sans Mono")

    def test_cjk_codes(self):
        self.assertEqual(len(CJK_CODES), 10)
        self.assertIn("ja", CJK_CODES)
        self.assertIn("ko", CJK_CODES)


class TestThemeStorage(unittest.TestCase):
    def setUp(self):
        import mark_editor.helpers as mh
        self._orig_config = mh.CONFIG_DIR
        self._orig_theme_file = mh.THEME_FILE
        self._tmp = Path(tempfile.mkdtemp())
        mh.CONFIG_DIR = self._tmp / ".config"
        mh.THEME_FILE = mh.CONFIG_DIR / "theme.json"

    def tearDown(self):
        import mark_editor.helpers as mh
        mh.CONFIG_DIR = self._orig_config
        mh.THEME_FILE = self._orig_theme_file

    def test_save_and_load_theme(self):
        save_theme("dark")
        self.assertEqual(load_theme(), "dark")

    def test_load_default_when_missing(self):
        self.assertEqual(load_theme(), DEFAULT_THEME)


class TestCacheDir(unittest.TestCase):
    def test_ensure_cache_dir(self):
        import mark_editor.helpers as mh
        orig = mh.CACHE_DIR
        try:
            tmp = Path(tempfile.mkdtemp())
            mh.CACHE_DIR = tmp / "mark_edit"
            path = ensure_cache_dir()
            self.assertTrue(path.exists())
            self.assertTrue(path.is_dir())
        finally:
            mh.CACHE_DIR = orig


class TestEditor(unittest.TestCase):
    """Behavioural tests that instantiate the real GTK4 application."""

    def setUp(self):
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("GtkSource", "5")

        import mark_editor.helpers as mh
        self._orig = (mh.CONFIG_DIR, mh.THEME_FILE, mh.CACHE_DIR)
        tmp = Path(tempfile.mkdtemp())
        mh.CONFIG_DIR = tmp / ".config"
        mh.THEME_FILE = mh.CONFIG_DIR / "theme.json"
        mh.CACHE_DIR = tmp / ".cache"

        try:
            from gi.repository import Adw, Gtk
            self._app = Adw.Application(application_id="com.github.mark_editor.test")
            self._app.register()
            from mark_editor.window import MarkEditorWindow
            self.app = MarkEditorWindow(application=self._app)
            self.app.present()
            from gi.repository import GLib
            GLib.idle_add(lambda: None)
        except Exception:
            self.skipTest("GTK4 display not available")

    def tearDown(self):
        import mark_editor.helpers as mh
        if hasattr(self, "app"):
            try:
                self.app.close()
            except Exception:
                pass
        mh.CONFIG_DIR, mh.THEME_FILE, mh.CACHE_DIR = self._orig

    def test_title(self):
        self.assertIn(APP_NAME, self.app.get_title())

    def test_heading(self):
        self.app._editor.set_text("text")
        self.app._on_heading(2)
        text = self.app._editor.get_text()
        self.assertTrue(text.startswith("## "))

    def test_paragraph(self):
        self.app._editor.set_text("## title")
        self.app._on_paragraph()
        text = self.app._editor.get_text()
        self.assertFalse(text.startswith("## "))

    def test_ordered_list(self):
        self.app._editor.set_text("item")
        self.app._on_ordered_list()
        text = self.app._editor.get_text()
        self.assertTrue(text.startswith("1. "))

    def test_unordered_list(self):
        self.app._editor.set_text("item")
        self.app._on_unordered_list()
        text = self.app._editor.get_text()
        self.assertTrue(text.startswith("* "))

    def test_blockquote(self):
        self.app._editor.set_text("quote")
        self.app._on_blockquote()
        text = self.app._editor.get_text()
        self.assertTrue(text.startswith("> "))

    def test_wrap_selection(self):
        self.app._editor.set_text("word")
        self.app._editor.select_all()
        self.app._wrap_selection("**")
        text = self.app._editor.get_text()
        self.assertEqual(text, "**word**")

    def test_zoom_in_out(self):
        size = self.app.editor_font_size
        self.app._on_zoom_in()
        self.assertEqual(self.app.editor_font_size, size + 2)
        self.app._on_zoom_out()
        self.assertEqual(self.app.editor_font_size, size)

    def test_toggle_theme(self):
        import mark_editor.helpers as mh
        start = mh.load_theme()
        expected = "dark" if start == "light" else "light"
        self.app._on_toggle_theme()
        self.assertEqual(mh.load_theme(), expected)

    def test_line_numbers(self):
        self.app._editor.set_text("a\nb\nc\n")
        self.app._editor.update_line_numbers()
        numbers = self.app._editor._gutter_buffer.get_text(
            self.app._editor._gutter_buffer.get_start_iter(),
            self.app._editor._gutter_buffer.get_end_iter(),
            include_hidden_chars=False,
        )
        self.assertEqual(numbers, "1\n2\n3\n4")

    def test_md_to_plain(self):
        text = md_to_plain("# Title\n\nSome **bold** and [link](https://x.com).")
        self.assertIn("Title", text)
        self.assertIn("Some bold and link.", text)

    def test_perform_convert_html(self):
        from mark_editor.helpers import md_to_html
        tmp = Path(tempfile.mkdtemp()) / "out.html"
        self.app._editor.set_text("# Hello")
        content = self.app._editor.get_text()
        html = md_to_html(content)
        tmp.write_text(html, encoding="utf-8")
        self.assertIn("<h1>", html)

    def test_perform_convert_txt(self):
        tmp = Path(tempfile.mkdtemp()) / "out.txt"
        self.app._editor.set_text("# Hello")
        content = self.app._editor.get_text()
        txt = md_to_plain(content)
        tmp.write_text(txt, encoding="utf-8")
        self.assertIn("Hello", txt)

    def test_save_to(self):
        tmp = Path(tempfile.mkdtemp()) / "doc.md"
        self.app._editor.set_text("hello world")
        text = self.app._editor.get_text()
        tmp.write_text(text, encoding="utf-8")
        self.assertEqual(tmp.read_text(encoding="utf-8"), "hello world")

    def test_quick_view_without_css(self):
        self.app._editor.set_text("# Hello")
        with unittest.mock.patch("mark_editor.window.webbrowser.open"):
            self.app._on_quick_view()
        html = (ensure_cache_dir() / TEMP_HTML).read_text(encoding="utf-8")
        self.assertIn("<h1>", html)
        self.assertNotIn("<style>", html)

    def test_quick_view_with_css(self):
        self.app._editor.set_text("# Hello")
        with unittest.mock.patch("mark_editor.window.webbrowser.open"):
            self.app._on_quick_view_css()
        html = (ensure_cache_dir() / TEMP_HTML).read_text(encoding="utf-8")
        self.assertIn("<h1>", html)
        self.assertIn("<style>", html)


class TestMarkdownConversion(unittest.TestCase):
    def test_converter_importable(self):
        from mark_editor.helpers import get_converter
        conv = get_converter()
        html = conv.convert("# Title")
        self.assertIn("<h1>", html)


if __name__ == "__main__":
    unittest.main()
