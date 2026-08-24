#!/usr/bin/env python3
"""Tests for Mark Editor 0.5.0."""

import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mark_editor import (
    APP_NAME,
    CJK_FONT_TAGS,
    DEFAULT_THEME,
    FONT_FAMILIES,
    RELEASE,
    TEMP_HTML,
    THEMES,
    VERSION,
    MarkEditor,
    ensure_cache_dir,
    load_theme,
    save_theme,
)


class TestAppMetadata(unittest.TestCase):
    def test_app_name(self):
        self.assertEqual(APP_NAME, "Mark Editor")

    def test_version(self):
        self.assertEqual(VERSION, "0.5.0")

    def test_release(self):
        self.assertEqual(RELEASE, "2026.08")

    def test_themes(self):
        self.assertIn("light", THEMES)
        self.assertIn("dark", THEMES)
        self.assertEqual(DEFAULT_THEME, "light")


class TestFontFamilies(unittest.TestCase):
    def test_categories_present(self):
        for category in (
            "sans",
            "mono",
            "symbola",
            "cjk_ja",
            "cjk_cn",
            "cjk_tw",
            "cjk_hk",
            "cjk_kr",
        ):
            self.assertIn(category, FONT_FAMILIES)
            self.assertIsInstance(FONT_FAMILIES[category], str)
            self.assertTrue(FONT_FAMILIES[category])

    def test_known_families(self):
        self.assertEqual(FONT_FAMILIES["sans"], "Noto Sans")
        self.assertEqual(FONT_FAMILIES["mono"], "Noto Sans Mono")
        self.assertEqual(FONT_FAMILIES["cjk_ja"], "Noto Sans Mono CJK JP")
        self.assertEqual(FONT_FAMILIES["cjk_cn"], "Noto Sans Mono CJK SC")
        self.assertEqual(FONT_FAMILIES["cjk_kr"], "Noto Sans Mono CJK KR")

    def test_language_tag_map(self):
        self.assertEqual(CJK_FONT_TAGS["ja"], "cjk_ja")
        for lang in ("zh-Hans", "zh-CN", "zh-Hans-CN"):
            self.assertEqual(CJK_FONT_TAGS[lang], "cjk_cn")
        for lang in ("zh-TW", "zh-Hant-TW"):
            self.assertEqual(CJK_FONT_TAGS[lang], "cjk_tw")
        for lang in ("zh-HK", "zh-Hant-HK"):
            self.assertEqual(CJK_FONT_TAGS[lang], "cjk_hk")
        for lang in ("ko", "ko-KR"):
            self.assertEqual(CJK_FONT_TAGS[lang], "cjk_kr")


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
        save_theme("dark")
        self.assertEqual(load_theme(), "dark")

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
        import mark_editor as me

        # Redirect config and cache to temp dirs so the tests never
        # touch real user data.
        self._orig = (me.CONFIG_DIR, me.THEME_FILE, me.CACHE_DIR)
        tmp = Path(tempfile.mkdtemp())
        me.CONFIG_DIR = tmp / ".config"
        me.THEME_FILE = me.CONFIG_DIR / "theme.json"
        me.CACHE_DIR = tmp / ".cache"

        try:
            self.app = MarkEditor()
            self.app.update_idletasks()
            self.app.update()
        except Exception:
            self.skipTest("Tkinter display not available")

    def tearDown(self):
        import mark_editor as me

        if hasattr(self, "app"):
            try:
                self.app.destroy()
            except Exception:
                pass
        me.CONFIG_DIR, me.THEME_FILE, me.CACHE_DIR = self._orig

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

    def test_language_fonts_tagged_region(self):
        import tkinter as tk

        ed = self.app._editor
        try:
            ed.delete("1.0", tk.END)
            ed.insert("1.0", "{:ja}\nこんにちは\n{:}\nafter")
            self.app._apply_language_fonts()
            ranges = ed.tag_ranges("cjk_ja")
            self.assertEqual(len(ranges), 2)
            self.assertEqual(ed.get(ranges[0], ranges[1]), "こんにちは\n")
            # block form for another language
            ed.delete("1.0", tk.END)
            ed.insert("1.0", "{:zh-Hans}\n中文\n{:}\nafter")
            self.app._apply_language_fonts()
            ranges = ed.tag_ranges("cjk_cn")
            self.assertEqual(len(ranges), 2)
            self.assertEqual(ed.get(ranges[0], ranges[1]), "中文\n")
            # unclosed marker applies only to the next line
            ed.delete("1.0", tk.END)
            ed.insert("1.0", "intro\n{:ko-KR}\n한국어\ntail")
            self.app._apply_language_fonts()
            ranges = ed.tag_ranges("cjk_kr")
            self.assertEqual(len(ranges), 2)
            self.assertEqual(ed.get(ranges[0], ranges[1]), "한국어")
            ed.delete("1.0", tk.END)
            self.app._apply_language_fonts()
        finally:
            ed.edit_modified(False)

    def test_cjk_codes_menu(self):
        mb = self.app.nametowidget(self.app.cget("menu"))
        fmt = None
        for i in range(1, mb.index("end") + 1):
            if mb.entrycget(i, "label") == "Format":
                fmt = mb.nametowidget(mb.entrycget(i, "menu"))
                break
        self.assertIsNotNone(fmt)
        idx = None
        for i in range(1, fmt.index("end") + 1):
            if fmt.type(i) == "cascade" and fmt.entrycget(i, "label") == "CJK Codes":
                idx = i
                break
        self.assertIsNotNone(idx)
        self.assertEqual(fmt.type(idx - 1), "separator")
        self.assertEqual(fmt.entrycget(idx + 1, "label"), "Emoji Shortcodes")
        cjk_menu = fmt.nametowidget(fmt.entrycget(idx, "menu"))
        self.assertEqual(cjk_menu.index("end"), 9)
        cjk_menu.invoke(1)
        self.assertIn("{:zh-Hans}", self.app._editor.get("1.0", "end"))

    def test_toggle_theme(self):
        import mark_editor as me

        start = me.load_theme()
        expected = "dark" if start == "light" else "light"
        self.app._on_toggle_theme()
        self.assertEqual(me.load_theme(), expected)
        self.assertTrue(self.app._restart_requested)

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
        text = self.app._md_to_plain(
            "# Title\n\nSome **bold** and [link](https://x.com)."
        )
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
        with unittest.mock.patch("mark_editor.CTkMessagebox"):
            self.app._save_to(tmp)
        self.assertEqual(tmp.read_text(encoding="utf-8"), "hello world")
        self.assertFalse(self.app.is_modified)

    def test_quick_view_without_css(self):
        self.app._editor.insert("1.0", "# Hello")
        with unittest.mock.patch("mark_editor.webbrowser.open"):
            self.app._on_quick_view()
        html = (ensure_cache_dir() / TEMP_HTML).read_text(encoding="utf-8")
        self.assertIn("<h1>", html)
        self.assertNotIn("<style>", html)

    def test_quick_view_with_css(self):
        self.app._editor.insert("1.0", "# Hello")
        with unittest.mock.patch("mark_editor.webbrowser.open"):
            self.app._on_quick_view_css()
        html = (ensure_cache_dir() / TEMP_HTML).read_text(encoding="utf-8")
        self.assertIn("<h1>", html)
        self.assertIn("<style>", html)


class TestDialogs(unittest.TestCase):
    def _root(self):
        try:
            import customtkinter as ctk

            root = ctk.CTk()
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
