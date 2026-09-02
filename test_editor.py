#!/usr/bin/env python3
"""Tests for Mark Editor 0.6.3 (GTK4)."""

import os
import sys
import tempfile
import unittest
import unittest.mock
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
        self.assertEqual(VERSION, "0.6.3")

    def test_release(self):
        """RELEASE matches the current release period."""
        self.assertEqual(RELEASE, "2026.09")

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
    """Behavioural tests that instantiate the real GTK4 application."""

    def setUp(self):
        """Isolate config dirs, then instantiate the GTK4 app window."""
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("GtkSource", "5")

        super().setUp()
        try:
            from gi.repository import Adw, GLib, Gtk

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
            try:
                self.app.close()
            except Exception:
                pass
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
        self.app._on_ordered_list()
        self.assertTrue(self.app._editor.get_text().startswith("1. "))

    def test_unordered_list(self):
        """Applying an unordered list prefixes the line with '* '."""
        self.app._editor.set_text("item")
        self.app._on_unordered_list()
        self.assertTrue(self.app._editor.get_text().startswith("* "))

    def test_blockquote(self):
        """Applying a blockquote prefixes the line with '> '."""
        self.app._editor.set_text("quote")
        self.app._on_blockquote()
        self.assertTrue(self.app._editor.get_text().startswith("> "))

    def test_wrap_selection(self):
        """Wrapping a selection surrounds it with the given marker."""
        self.app._editor.set_text("word")
        self.app._editor.select_all()
        self.app._wrap_selection("**")
        self.assertEqual(self.app._editor.get_text(), "**word**")

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

    def test_line_numbers(self):
        """The gutter buffer reflects the editor's line count."""
        self.app._editor.set_text("a\nb\nc\n")
        self.app._editor.update_line_numbers()
        numbers = self.app._editor._gutter_buffer.get_text(
            self.app._editor._gutter_buffer.get_start_iter(),
            self.app._editor._gutter_buffer.get_end_iter(),
            include_hidden_chars=False,
        )
        self.assertEqual(numbers, "1\n2\n3\n4")

    def test_md_to_plain(self):
        """md_to_plain strips Markdown markup and keeps the text."""
        text = md_to_plain("# Title\n\nSome **bold** and [link](https://x.com).")
        self.assertIn("Title", text)
        self.assertIn("Some bold and link.", text)

    def test_perform_convert_html(self):
        """md_to_html produces HTML5 heading markup."""
        self.app._editor.set_text("# Hello")
        html = md_to_html(self.app._editor.get_text())
        self.assertIn("<h1>", html)

    def test_perform_convert_txt(self):
        """md_to_plain converts Markdown to readable text."""
        self.app._editor.set_text("# Hello")
        txt = md_to_plain(self.app._editor.get_text())
        self.assertIn("Hello", txt)

    def test_save_to(self):
        """Editor text writes to a file and reads back unchanged."""
        tmp = Path(tempfile.mkdtemp()) / "doc.md"
        self.app._editor.set_text("hello world")
        tmp.write_text(self.app._editor.get_text(), encoding="utf-8")
        self.assertEqual(tmp.read_text(encoding="utf-8"), "hello world")

    def test_quick_view_without_css(self):
        """Quick view renders HTML5 output without embedded CSS."""
        self.app._editor.set_text("# Hello")
        with unittest.mock.patch("mark_editor.window.webbrowser.open"):
            self.app._on_quick_view()
        html = (ensure_cache_dir() / "Temp.html").read_text(encoding="utf-8")
        self.assertIn("<h1>", html)
        self.assertNotIn("<style>", html)

    def test_quick_view_with_css(self):
        """Quick view with CSS renders HTML5 output with embedded styles."""
        self.app._editor.set_text("# Hello")
        with unittest.mock.patch("mark_editor.window.webbrowser.open"):
            self.app._on_quick_view_css()
        html = (ensure_cache_dir() / "Temp.html").read_text(encoding="utf-8")
        self.assertIn("<h1>", html)
        self.assertIn("<style>", html)


class TestMarkdownConversion(unittest.TestCase):
    """Verify the Markdown converter is importable and functional."""

    def test_converter_importable(self):
        """get_converter returns a converter that emits HTML5 heading markup."""
        html = get_converter().convert("# Title")
        self.assertIn("<h1>", html)


if __name__ == "__main__":
    unittest.main()
