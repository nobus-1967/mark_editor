#!/usr/bin/env python3
"""Tests for Mark Editor."""

import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mark_editor import (
    __app_name__,
    __version__,
    font_installed,
    resolve_font,
    TkHTMLRenderer,
)


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

    def test_font_installed(self):
        result = font_installed("__nonexistent_font_xyz__")
        self.assertFalse(result)

    def test_font_installed_system(self):
        result = font_installed("Courier")
        self.assertIsInstance(result, bool)

    def test_resolve_font_fallback(self):
        font = resolve_font("Mono", "__nonexistent__", "Liberation Mono", "Courier", 14)
        self.assertIsNotNone(font)
        self.assertEqual(font.actual("size"), 14)

    def test_resolve_font_user(self):
        font = resolve_font("Mono", "Courier", "Liberation Mono", "Courier", 12)
        self.assertIsNotNone(font)
        self.assertEqual(font.actual("size"), 12)


class TestAppMetadata(unittest.TestCase):
    def test_app_name(self):
        self.assertEqual(__app_name__, "Mark Editor")

    def test_version(self):
        self.assertEqual(__version__, "0.3")


class TestTkHTMLRenderer(unittest.TestCase):
    def setUp(self):
        try:
            import tkinter as tk

            self.root = tk.Tk()
            self.root.withdraw()
            from tkinter.font import Font

            self.text = tk.Text(self.root)
            self.body_font = Font(family="Times", size=14)
            self.code_font = Font(family="Courier", size=14)
            self.renderer = TkHTMLRenderer(
                self.text, self.body_font, ("Sans", "Noto Sans"), self.code_font
            )
        except Exception:
            self.skipTest("Tkinter not available")

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()

    def test_simple_paragraph(self):
        html = "<p>Hello world</p>"
        self.renderer.feed(html)
        self.renderer.close()
        content = self.text.get("1.0", "end-1c")
        self.assertIn("Hello world", content)

    def test_bold(self):
        html = "<p><strong>Bold</strong> text</p>"
        self.renderer.feed(html)
        self.renderer.close()
        content = self.text.get("1.0", "end-1c")
        self.assertIn("Bold text", content)

    def test_heading(self):
        html = "<h1>Title</h1>"
        self.renderer.feed(html)
        self.renderer.close()
        content = self.text.get("1.0", "end-1c")
        self.assertIn("Title", content)

    def test_link(self):
        html = '<p><a href="https://example.com">click</a></p>'
        self.renderer.feed(html)
        self.renderer.close()
        content = self.text.get("1.0", "end-1c")
        self.assertIn("click", content)

    def test_image_replacement(self):
        html = '<img src="test.png" alt="alt text">'
        self.renderer.feed(html)
        self.renderer.close()
        content = self.text.get("1.0", "end-1c")
        self.assertIn("alt text", content)

    def test_hr(self):
        html = "<hr>"
        self.renderer.feed(html)
        self.renderer.close()
        content = self.text.get("1.0", "end-1c")
        self.assertTrue(len(content.strip()) > 0)

    def test_ruby_furigana(self):
        html = "<p><ruby>\u65e5\u672c<rt>\u306b\u307b\u3093</rt></ruby></p>"
        self.renderer.feed(html)
        self.renderer.close()
        content = self.text.get("1.0", "end-1c")
        self.assertIn("\u65e5\u672c", content)
        self.assertIn("\u306b\u307b\u3093", content)

    def test_ruby_wo_rt(self):
        html = "<p><ruby>\u65e5\u672c</ruby></p>"
        self.renderer.feed(html)
        self.renderer.close()
        content = self.text.get("1.0", "end-1c")
        self.assertIn("\u65e5\u672c", content)


class TestDialogs(unittest.TestCase):
    def test_table_dialog_creation(self):
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            from mark_editor import TableDialog

            dlg = TableDialog(root)
            self.assertIsNotNone(dlg)
            dlg.destroy()
            root.destroy()
        except Exception:
            self.skipTest("Tkinter not available")

    def test_furigana_dialog_creation(self):
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            from mark_editor import FuriganaDialog

            dlg = FuriganaDialog(root)
            self.assertIsNotNone(dlg)
            dlg.destroy()
            root.destroy()
        except Exception:
            self.skipTest("Tkinter not available")

    def test_header_link_dialog_creation(self):
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            from mark_editor import HeaderLinkDialog

            dlg = HeaderLinkDialog(root)
            self.assertIsNotNone(dlg)
            dlg.destroy()
            root.destroy()
        except Exception:
            self.skipTest("Tkinter not available")


class TestFindDialog(unittest.TestCase):
    def test_dialog_creation(self):
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            text = tk.Text(root)
            from mark_editor import FindDialog

            dlg = FindDialog(root, text)
            self.assertIsNotNone(dlg)
            dlg.destroy()
            root.destroy()
        except Exception:
            self.skipTest("Tkinter not available")


class TestReplaceDialog(unittest.TestCase):
    def test_dialog_creation(self):
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            text = tk.Text(root)
            from mark_editor import ReplaceDialog

            dlg = ReplaceDialog(root, text)
            self.assertIsNotNone(dlg)
            dlg.destroy()
            root.destroy()
        except Exception:
            self.skipTest("Tkinter not available")


class TestMarkdownRendering(unittest.TestCase):
    def test_basic_markdown(self):
        import markdown

        html = markdown.markdown("Hello **world**")
        self.assertIn("<strong>world</strong>", html)
        self.assertIn("<p>", html)

    def test_headings(self):
        import markdown

        for level in range(1, 7):
            md = f"{'#' * level} Heading {level}"
            html = markdown.markdown(md)
            self.assertIn(f"<h{level}>", html)

    def test_lists(self):
        import markdown

        md = "* item 1\n* item 2"
        html = markdown.markdown(md)
        self.assertIn("<ul>", html)
        self.assertIn("<li>", html)

    def test_code_block(self):
        import markdown

        md = "```python\nprint('hi')\n```"
        html = markdown.markdown(md, extensions=["fenced_code"])
        self.assertIn("<code", html)


class TestModuleImports(unittest.TestCase):
    def test_markdown_importable(self):
        import markdown

        self.assertTrue(hasattr(markdown, "markdown"))

    def test_pymdownx_importable(self):
        import pymdownx

        self.assertIsNotNone(pymdownx)


if __name__ == "__main__":
    unittest.main()
