"""Mark Editor — a simple Markdown editor.

The editor is written as a single Python 3 file using Tkinter and
ttkbootstrap. It uses the markdown2html5-base library to convert Markdown
into HTML5 for export and for the Quick view in the browser, and
markdown2pdf-base to export documents as PDF (via pandoc + xelatex).
"""

from __future__ import annotations

import json
import os
import re
import sys
import webbrowser
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from tkinter import font as tkfont
from typing import Optional

import ttkbootstrap as tb
from markdown2html5_base import MarkdownToHTML
from markdown2pdf_base import convert as md2pdf_convert
from ttkbootstrap.dialogs import Messagebox, Querybox

# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

APP_NAME = "Mark Editor"
VERSION = "0.4.2"
RELEASE = "2026.08"

CONFIG_DIR = Path.home() / ".config" / "mark_editor"
THEME_FILE = CONFIG_DIR / "theme.json"

CACHE_DIR = Path.home() / ".cache" / "mark_edit"
TEMP_MD = "~temp.md"
TEMP_HTML = "temp.html"

# 15 ttkbootstrap 2.0 themes (light / dark pairs).
THEMES: list[str] = [
    "bootstrap-light",
    "bootstrap-dark",
    "catppuccin-light",
    "catppuccin-dark",
    "dracula-light",
    "dracula-dark",
    "everforest-light",
    "everforest-dark",
    "gruvbox-light",
    "gruvbox-dark",
    "minty-light",
    "minty-dark",
    "nord-light",
    "nord-dark",
    "one-light",
    "one-dark",
    "pulse-light",
    "pulse-dark",
    "pydata-light",
    "pydata-dark",
    "sandstone-light",
    "sandstone-dark",
    "solarized-light",
    "solarized-dark",
    "tokyo-night-light",
    "tokyo-night-dark",
    "united-light",
    "united-dark",
    "vapor-light",
    "vapor-dark",
]

DEFAULT_THEME = "bootstrap-light"

# Emoji shortcodes (must match the ones supported by markdown2html5-base).
EMOJIS: list[str] = [
    "joy",
    "smile",
    "heart",
    "thumbsup",
    "thumbsdown",
    "wink",
    "tada",
    "rocket",
    "fire",
    "star",
    "cry",
    "thinking",
    "100",
    "sparkles",
    "eyes",
    "bulb",
    "warning",
    "ok",
    "check_mark",
]

# Special signs for the Format → Special Signs submenu (name → inserted code).
SPECIAL_SIGNS: list[tuple[str, str]] = [
    ("copyright", "(c)"),
    ("trademark", "(tm)"),
    ("registered trademark", "(r)"),
    ("plus-minus", "+/-"),
    ("not equal to", "!="),
    ("logical equivalence", "<=>"),
    ("less-than/equal to", "<="),
    ("greater-than/equal to", ">="),
    ("left arrow", "->"),
    ("right arrow", "<-"),
    ("up arrow", ":uparrow:"),
    ("down arrow", ":dnarrow:"),
    ("logical implication", "=>"),
    ("slash", ":slash:"),
    ("backslash", ":bslash:"),
    ("left angle quote", "<<"),
    ("right angle quote", ">>"),
    ("em dash", "---"),
    ("en dash", "--"),
    ("ellipsis", "..."),
]

# CJK language codes for the Format → CJK Codes submenu (inserted as {:code}).
CJK_CODES: list[str] = [
    "ja",
    "zh-Hans",
    "zh-CN",
    "zh-Hans-CN",
    "zh-TW",
    "zh-Hant-TW",
    "zh-HK",
    "zh-Hant-HK",
    "ko",
    "ko-KR",
]

# Font fallback chains per category (user typeface → free fonts → general).
FONT_FALLBACKS: dict[str, list[str]] = {
    "sans": ["Noto Sans", "DejaVu Sans", "Liberation Sans", "Arial"],
    "serif": ["Noto Serif", "DejaVu Serif", "Liberation Serif", "Times"],
    "mono": [
        "Noto Sans Mono",
        "DejaVu Sans Mono",
        "Liberation Mono",
        "Courier",
    ],
    "symbola": [
        "Symbola",
        "Segoe UI Symbol",
        "Segoe UI Emoji",
    ],
    "cjk": ["Noto Sans CJK JP", "DejaVu Sans", "Sarasa Gothic", "Meiryo"],
}

INTERFACE_FONT_SIZE = 14
STATUS_FONT_SIZE = 12
EDITOR_FONT_SIZE = 12
ZOOM_STEP = 2


# ═══════════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════════


def resource_path(relative: str) -> str:
    """Return an absolute path for a bundled resource (PyInstaller aware)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def font_installed(family: str) -> bool:
    """Return True if the given font family exists on the system."""
    try:
        available = {f.lower() for f in tkfont_families()}
        return family.lower() in available
    except Exception:
        return True


_font_cache: list[str] = []


def tkfont_families() -> list[str]:
    """Return the list of installed font families (cached)."""
    if not _font_cache:
        try:
            _font_cache.extend(tkfont.families())
        except Exception:
            _font_cache.extend(["Noto Sans", "DejaVu Sans", "Courier"])
    return _font_cache


def resolve_font(category: str) -> str:
    """Return the first installed font family for the given category."""
    for family in FONT_FALLBACKS.get(category, FONT_FALLBACKS["sans"]):
        if font_installed(family):
            return family
    return FONT_FALLBACKS["sans"][-1]


def load_theme() -> str:
    """Load the saved theme from ~/.config/mark_editor/theme.json."""
    try:
        data = json.loads(THEME_FILE.read_text(encoding="utf-8"))
        name = data.get("theme", DEFAULT_THEME)
        if name in THEMES:
            return name
    except Exception:
        pass
    return DEFAULT_THEME


def save_theme(name: str) -> None:
    """Save the current theme to ~/.config/mark_editor/theme.json."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        THEME_FILE.write_text(
            json.dumps({"theme": name}, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def ensure_cache_dir() -> Path:
    """Create and return ~/.cache/mark_edit."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR



# ═══════════════════════════════════════════════════════════════════════
# Dialog classes
# ═══════════════════════════════════════════════════════════════════════


class FindDialog(tb.Toplevel):
    """Simple find dialog with regex support."""

    def __init__(self, parent: tk.Tk, text_widget: tk.Text) -> None:
        super().__init__(parent)
        self.title("Find")
        self.resizable(False, False)
        self.text = text_widget
        self.use_regex = tb.BooleanVar(value=False)

        tb.Label(self, text="Find:").grid(
            row=0, column=0, sticky="e", padx=8, pady=6
        )
        self.find_var = tb.StringVar()
        self.entry = tb.Entry(self, textvariable=self.find_var, width=30)
        self.entry.grid(row=0, column=1, columnspan=2, padx=4, pady=6)
        self.entry.focus_set()

        tb.Checkbutton(
            self, text="Use regex", variable=self.use_regex, bootstyle="round-toggle"
        ).grid(row=1, column=1, columnspan=2, sticky="w", padx=4)

        btn = tb.Frame(self)
        btn.grid(row=2, column=0, columnspan=3, pady=8)
        tb.Button(btn, text="Find Next", command=self.find_next, bootstyle="primary"
                  ).pack(side=tk.LEFT, padx=4)
        tb.Button(btn, text="Close", command=self.destroy).pack(
            side=tk.LEFT, padx=4
        )

        self.bind("<Return>", lambda e: self.find_next())
        self.bind("<Escape>", lambda e: self.destroy())

    def _get_pattern(self) -> Optional[re.Pattern]:
        term = self.find_var.get()
        if not term:
            return None
        try:
            if self.use_regex.get():
                return re.compile(term)
            return re.compile(re.escape(term))
        except re.error:
            return None

    def _clear_highlights(self) -> None:
        self.text.tag_remove("find", "1.0", tk.END)

    def find_next(self) -> bool:
        self._clear_highlights()
        pattern = self._get_pattern()
        if not pattern:
            return False
        start = self.text.index(tk.INSERT)
        found = self._search_from(pattern, start)
        if not found:
            found = self._search_from(pattern, "1.0")
        return found is not None

    def _search_from(self, pattern: re.Pattern, start: str) -> Optional[str]:
        text = self.text.get("1.0", tk.END)
        start_pos = self.text.index(start)
        offset = self._index_to_offset(start_pos, text)
        match = pattern.search(text, offset)
        if not match:
            return None
        pos = self._offset_to_index(match.start(), text)
        end = self._offset_to_index(match.end(), text)
        self.text.tag_add("find", pos, end)
        self.text.tag_configure("find", background="#fff3cd", foreground="#212529")
        self.text.mark_set(tk.INSERT, end)
        self.text.see(end)
        return pos

    def _index_to_offset(self, index: str, text: str) -> int:
        line, col = index.split(".")
        offset = 0
        for i in range(1, int(line)):
            offset += len(text.split("\n")[i - 1]) + 1
        return offset + int(col)

    def _offset_to_index(self, offset: int, text: str) -> str:
        before = text[:offset]
        return f"{before.count(chr(10)) + 1}.{len(before) - before.rfind(chr(10)) - 1}"


class ReplaceDialog(tb.Toplevel):
    """Replace dialog with manual control and a 'Replace All' button."""

    def __init__(self, parent: tk.Tk, text_widget: tk.Text) -> None:
        super().__init__(parent)
        self.title("Replace")
        self.resizable(False, False)
        self.text = text_widget
        self.use_regex = tb.BooleanVar(value=False)

        tb.Label(self, text="Find:").grid(row=0, column=0, sticky="e", padx=8, pady=6)
        self.find_var = tb.StringVar()
        tb.Entry(self, textvariable=self.find_var, width=30).grid(
            row=0, column=1, columnspan=2, padx=4, pady=6
        )

        tb.Label(self, text="Replace:").grid(
            row=1, column=0, sticky="e", padx=8, pady=6
        )
        self.replace_var = tb.StringVar()
        tb.Entry(self, textvariable=self.replace_var, width=30).grid(
            row=1, column=1, columnspan=2, padx=4, pady=6
        )

        tb.Checkbutton(
            self, text="Use regex", variable=self.use_regex, bootstyle="round-toggle"
        ).grid(row=2, column=1, columnspan=2, sticky="w", padx=4)

        btn = tb.Frame(self)
        btn.grid(row=3, column=0, columnspan=3, pady=8)
        tb.Button(btn, text="Replace", command=self.replace_one, bootstyle="primary"
                  ).pack(side=tk.LEFT, padx=3)
        tb.Button(btn, text="Replace All", command=self.replace_all).pack(
            side=tk.LEFT, padx=3
        )
        tb.Button(btn, text="Find Next", command=self.find_next).pack(
            side=tk.LEFT, padx=3
        )
        tb.Button(btn, text="Close", command=self.destroy).pack(side=tk.LEFT, padx=3)

        self.bind("<Return>", lambda e: self.replace_one())
        self.bind("<Escape>", lambda e: self.destroy())

    def _get_pattern(self) -> Optional[re.Pattern]:
        term = self.find_var.get()
        if not term:
            return None
        try:
            return re.compile(term if self.use_regex.get() else re.escape(term))
        except re.error:
            return None

    def _clear_highlights(self) -> None:
        self.text.tag_remove("find", "1.0", tk.END)

    def find_next(self) -> bool:
        self._clear_highlights()
        pattern = self._get_pattern()
        if not pattern:
            return False
        start = self.text.index(tk.INSERT)
        found = self._find_from(pattern, start)
        if not found:
            found = self._find_from(pattern, "1.0")
        return found is not None

    def _find_from(self, pattern: re.Pattern, start: str) -> Optional[str]:
        content = self.text.get("1.0", tk.END)
        offset = self._index_to_offset(start, content)
        match = pattern.search(content, offset)
        if not match:
            return None
        pos = self._offset_to_index(match.start(), content)
        end = self._offset_to_index(match.end(), content)
        self.text.tag_add("find", pos, end)
        self.text.tag_configure("find", background="#fff3cd", foreground="#212529")
        self.text.mark_set(tk.INSERT, end)
        self.text.see(end)
        return pos

    def _index_to_offset(self, index: str, text: str) -> int:
        line, col = index.split(".")
        offset = 0
        lines = text.split("\n")
        for i in range(1, int(line)):
            offset += len(lines[i - 1]) + 1
        return offset + int(col)

    def _offset_to_index(self, offset: int, text: str) -> str:
        before = text[:offset]
        return f"{before.count(chr(10)) + 1}.{len(before) - before.rfind(chr(10)) - 1}"

    def replace_one(self) -> None:
        pattern = self._get_pattern()
        if not pattern:
            return
        content = self.text.get("1.0", tk.END)
        cursor = self.text.index(tk.INSERT)
        offset = self._index_to_offset(cursor, content)
        match = pattern.search(content, offset)
        if not match:
            match = pattern.search(content)
        if not match:
            return
        start = self._offset_to_index(match.start(), content)
        end = self._offset_to_index(match.end(), content)
        self.text.delete(start, end)
        self.text.insert(start, self.replace_var.get())
        self.text.mark_set(tk.INSERT, start)
        self.text.see(start)
        self._clear_highlights()

    def replace_all(self) -> None:
        pattern = self._get_pattern()
        if not pattern:
            return
        content = self.text.get("1.0", tk.END)
        if self.use_regex.get():
            new = pattern.sub(self.replace_var.get(), content)
        else:
            new = content.replace(self.find_var.get(), self.replace_var.get())
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", new)
        self._clear_highlights()


class TableDialog(tb.Toplevel):
    """Dialog to create a Markdown table with optional footer."""

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("Insert Table")
        self.resizable(False, False)
        self.cols_var = tb.IntVar(value=3)
        self.rows_var = tb.IntVar(value=3)
        self.footer_var = tb.BooleanVar(value=True)

        tb.Label(self, text="Columns:").grid(row=0, column=0, sticky="e", padx=8, pady=6)
        tb.Spinbox(self, from_=1, to=20, textvariable=self.cols_var, width=5).grid(
            row=0, column=1, padx=4, pady=6
        )

        tb.Label(self, text="Rows:").grid(row=1, column=0, sticky="e", padx=8, pady=6)
        tb.Spinbox(self, from_=1, to=50, textvariable=self.rows_var, width=5).grid(
            row=1, column=1, padx=4, pady=6
        )

        tb.Checkbutton(self, text="Add footer", variable=self.footer_var).grid(
            row=2, column=0, columnspan=2, padx=8, pady=4
        )

        btn = tb.Frame(self)
        btn.grid(row=3, column=0, columnspan=2, pady=8)
        tb.Button(btn, text="Insert", command=self._insert, bootstyle="primary"
                  ).pack(side=tk.LEFT, padx=4)
        tb.Button(btn, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=4)

        self.bind("<Return>", lambda e: self._insert())
        self.bind("<Escape>", lambda e: self.destroy())

    def _insert(self) -> None:
        cols = self.cols_var.get()
        rows = self.rows_var.get()
        use_footer = self.footer_var.get()

        header = "| " + " | ".join(f"Header {i + 1}" for i in range(cols)) + " |"
        align = "| " + " | ".join(":---:" for _ in range(cols)) + " |"
        lines = ["", header, align]
        for r in range(rows):
            lines.append("| " + " | ".join(f"Cell {r + 1}-{c + 1}" for c in range(cols)) + " |")
        if use_footer:
            lines.append("| " + " | ".join("=" * 8 for _ in range(cols)) + " |")
            lines.append("| " + " | ".join(f"Footer {c + 1}" for c in range(cols)) + " |")
        self.callback("\n".join(lines))
        self.destroy()


class FuriganaDialog(tb.Toplevel):
    """Dialog to insert a ruby annotation (furigana)."""

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("Furigana (Ruby Annotation)")
        self.resizable(False, False)

        tb.Label(self, text="Kanji / Text:").grid(row=0, column=0, sticky="e", padx=8, pady=6)
        self.kanji_var = tb.StringVar()
        tb.Entry(self, textvariable=self.kanji_var, width=30).grid(
            row=0, column=1, padx=4, pady=6
        )

        tb.Label(self, text="Reading (ruby):").grid(
            row=1, column=0, sticky="e", padx=8, pady=6
        )
        self.reading_var = tb.StringVar()
        tb.Entry(self, textvariable=self.reading_var, width=30).grid(
            row=1, column=1, padx=4, pady=6
        )

        btn = tb.Frame(self)
        btn.grid(row=2, column=0, columnspan=2, pady=8)
        tb.Button(btn, text="Insert", command=self._insert, bootstyle="primary"
                  ).pack(side=tk.LEFT, padx=4)
        tb.Button(btn, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=4)

        self.bind("<Return>", lambda e: self._insert())
        self.bind("<Escape>", lambda e: self.destroy())

    def _insert(self) -> None:
        kanji = self.kanji_var.get().strip()
        reading = self.reading_var.get().strip()
        if kanji and reading:
            self.callback(f"{{{kanji} | {reading}}}")
        self.destroy()


class HeaderLinkDialog(tb.Toplevel):
    """Dialog to insert a link to a header with ID."""

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("Insert Header Link")
        self.resizable(False, False)

        tb.Label(self, text="Header ID:").grid(row=0, column=0, sticky="e", padx=8, pady=6)
        self.id_var = tb.StringVar()
        tb.Entry(self, textvariable=self.id_var, width=30).grid(
            row=0, column=1, padx=4, pady=6
        )

        tb.Label(self, text="Link text:").grid(row=1, column=0, sticky="e", padx=8, pady=6)
        self.text_var = tb.StringVar()
        tb.Entry(self, textvariable=self.text_var, width=30).grid(
            row=1, column=1, padx=4, pady=6
        )

        btn = tb.Frame(self)
        btn.grid(row=2, column=0, columnspan=2, pady=8)
        tb.Button(btn, text="Insert", command=self._insert, bootstyle="primary"
                  ).pack(side=tk.LEFT, padx=4)
        tb.Button(btn, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=4)

        self.bind("<Return>", lambda e: self._insert())
        self.bind("<Escape>", lambda e: self.destroy())

    def _insert(self) -> None:
        hid = self.id_var.get().strip()
        text = self.text_var.get().strip() or hid
        if hid:
            self.callback(f"[{text}](#{hid})")
        self.destroy()


class FootnoteDialog(tb.Toplevel):
    """Dialog to create a footnote reference and its definition."""

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("Insert Footnote")
        self.resizable(False, False)

        tb.Label(self, text="Reference / Name:").grid(
            row=0, column=0, sticky="e", padx=8, pady=6
        )
        self.ref_var = tb.StringVar()
        tb.Entry(self, textvariable=self.ref_var, width=30).grid(
            row=0, column=1, padx=4, pady=6
        )

        tb.Label(self, text="Definition:").grid(
            row=1, column=0, sticky="e", padx=8, pady=6
        )
        self.def_var = tb.StringVar()
        tb.Entry(self, textvariable=self.def_var, width=30).grid(
            row=1, column=1, padx=4, pady=6
        )

        btn = tb.Frame(self)
        btn.grid(row=2, column=0, columnspan=2, pady=8)
        tb.Button(btn, text="Insert", command=self._insert, bootstyle="primary"
                  ).pack(side=tk.LEFT, padx=4)
        tb.Button(btn, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=4)

        self.bind("<Return>", lambda e: self._insert())
        self.bind("<Escape>", lambda e: self.destroy())

    def _insert(self) -> None:
        ref = self.ref_var.get().strip()
        definition = self.def_var.get().strip()
        if ref:
            self.callback(ref, definition)
        self.destroy()


class DefinitionListDialog(tb.Toplevel):
    """Dialog to create a definition list (term + up to 2 definitions)."""

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("Definition List")
        self.resizable(False, False)

        tb.Label(self, text="Term:").grid(row=0, column=0, sticky="ne", padx=8, pady=6)
        self.term_var = tb.StringVar()
        tb.Entry(self, textvariable=self.term_var, width=30).grid(
            row=0, column=1, padx=4, pady=6
        )

        tb.Label(self, text="Definition 1:").grid(
            row=1, column=0, sticky="e", padx=8, pady=6
        )
        self.def1_var = tb.StringVar()
        tb.Entry(self, textvariable=self.def1_var, width=30).grid(
            row=1, column=1, padx=4, pady=6
        )

        tb.Label(self, text="Definition 2:").grid(
            row=2, column=0, sticky="e", padx=8, pady=6
        )
        self.def2_var = tb.StringVar()
        tb.Entry(self, textvariable=self.def2_var, width=30).grid(
            row=2, column=1, padx=4, pady=6
        )

        btn = tb.Frame(self)
        btn.grid(row=3, column=0, columnspan=2, pady=8)
        tb.Button(btn, text="Insert", command=self._insert, bootstyle="primary"
                  ).pack(side=tk.LEFT, padx=4)
        tb.Button(btn, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=4)

        self.bind("<Return>", lambda e: self._insert())
        self.bind("<Escape>", lambda e: self.destroy())

    def _insert(self) -> None:
        term = self.term_var.get().strip()
        defs = [d for d in (self.def1_var.get().strip(), self.def2_var.get().strip()) if d]
        if term and defs:
            lines = [f"", term]
            lines.extend(f": {d}" for d in defs)
            self.callback("\n".join(lines))
        self.destroy()


class YAMLFrontMatterDialog(tb.Toplevel):
    """Dialog to add a YAML Front Matter block at the start of the document."""

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("YAML Front Matter")
        self.resizable(False, False)

        fields = ["lang", "title", "author", "description", "keywords"]
        self.vars: dict[str, tb.StringVar] = {}
        for i, field in enumerate(fields):
            tb.Label(self, text=f"{field}:").grid(
                row=i, column=0, sticky="e", padx=8, pady=4
            )
            self.vars[field] = tb.StringVar()
            tb.Entry(self, textvariable=self.vars[field], width=35).grid(
                row=i, column=1, padx=4, pady=4
            )

        btn = tb.Frame(self)
        btn.grid(row=len(fields), column=0, columnspan=2, pady=8)
        tb.Button(btn, text="Insert", command=self._insert, bootstyle="primary"
                  ).pack(side=tk.LEFT, padx=4)
        tb.Button(btn, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=4)

        self.bind("<Return>", lambda e: self._insert())
        self.bind("<Escape>", lambda e: self.destroy())

    def _insert(self) -> None:
        lines = ["---"]
        for field in ["lang", "title", "author", "description", "keywords"]:
            value = self.vars[field].get().strip()
            if value:
                lines.append(f"{field}: {value}")
        lines.append(f"published: {datetime.now().date().isoformat()}")
        lines.append("---")
        self.callback("\n".join(lines))
        self.destroy()


class DateTimeDialog(tb.Toplevel):
    """Dialog to insert the system date and/or time."""

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("Insert Date and Time")
        self.resizable(False, False)
        self.choice = tb.StringVar(value="date_time")

        tb.Radiobutton(
            self, text="Date and time", variable=self.choice, value="date_time"
        ).grid(row=0, column=0, sticky="w", padx=12, pady=4)
        tb.Radiobutton(
            self, text="Date only", variable=self.choice, value="date"
        ).grid(row=1, column=0, sticky="w", padx=12, pady=4)
        tb.Radiobutton(
            self, text="Time only", variable=self.choice, value="time"
        ).grid(row=2, column=0, sticky="w", padx=12, pady=4)

        btn = tb.Frame(self)
        btn.grid(row=3, column=0, pady=8)
        tb.Button(btn, text="Insert", command=self._insert, bootstyle="primary"
                  ).pack(side=tk.LEFT, padx=4)
        tb.Button(btn, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=4)

        self.bind("<Return>", lambda e: self._insert())
        self.bind("<Escape>", lambda e: self.destroy())

    def _insert(self) -> None:
        now = datetime.now()
        choice = self.choice.get()
        if choice == "date_time":
            value = now.strftime("%Y-%m-%d %H:%M:%S")
        elif choice == "date":
            value = now.strftime("%Y-%m-%d")
        else:
            value = now.strftime("%H:%M:%S")
        self.callback(value)
        self.destroy()


# ═══════════════════════════════════════════════════════════════════════
# Main application
# ═══════════════════════════════════════════════════════════════════════


class MarkEditor(tb.App):
    """The main Mark Editor application window."""

    def __init__(self) -> None:
        theme = load_theme()
        super().__init__(themename=theme, title=APP_NAME)

        self.converter = MarkdownToHTML()
        self.current_file: Optional[Path] = None
        self.is_modified = False
        self.editor_font_size = EDITOR_FONT_SIZE
        self.interface_font_size = INTERFACE_FONT_SIZE

        # Resolve fonts.
        self.interface_font = (resolve_font("sans"), self.interface_font_size, "normal")
        self.editor_font = (resolve_font("mono"), self.editor_font_size, "normal")
        self.editor_mono = (resolve_font("mono"), self.editor_font_size - 1, "normal")

        self._build_menu()
        self._build_statusbar()
        self._build_panels()
        self._bind_shortcuts()
        self._update_title()
        self._update_status()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menubar = tb.Menu(self)

        # ── File ──
        file_menu = tb.Menu(menubar, tearoff=False)
        file_menu.add_command(label="New File", accelerator="Ctrl+N", command=self._on_new)
        file_menu.add_separator()
        file_menu.add_command(label="Open...", accelerator="Ctrl+O", command=self._on_open)
        file_menu.add_command(
            label="Reopen", accelerator="Ctrl+Shift+O", command=self._on_reopen
        )
        file_menu.add_separator()
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self._on_save)
        file_menu.add_command(
            label="Save As...", accelerator="Ctrl+Shift+S", command=self._on_save_as
        )
        file_menu.add_command(
            label="Convert...", accelerator="Ctrl+E", command=self._on_convert
        )
        file_menu.add_separator()
        file_menu.add_command(label="Quit", accelerator="Ctrl+Q", command=self._on_quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # ── Edit ──
        edit_menu = tb.Menu(menubar, tearoff=False)
        edit_menu.add_command(label="Undo", accelerator="Ctrl+Z", command=self._on_undo)
        edit_menu.add_command(
            label="Redo", accelerator="Ctrl+Shift+Z", command=self._on_redo
        )
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", accelerator="Ctrl+X", command=self._on_cut)
        edit_menu.add_command(label="Copy", accelerator="Ctrl+C", command=self._on_copy)
        edit_menu.add_command(label="Paste", accelerator="Ctrl+V", command=self._on_paste)
        edit_menu.add_separator()
        edit_menu.add_command(label="Find...", accelerator="Ctrl+F", command=self._on_find)
        edit_menu.add_command(
            label="Replace...", accelerator="Ctrl+R", command=self._on_replace
        )
        edit_menu.add_command(
            label="Replace All...", accelerator="Ctrl+Shift+R",
            command=self._on_replace_all,
        )
        edit_menu.add_separator()
        edit_menu.add_command(
            label="Select All", accelerator="Ctrl+A", command=self._on_select_all
        )
        edit_menu.add_command(
            label="Remove Selection", accelerator="Ctrl+Shift+A",
            command=self._on_remove_selection,
        )
        edit_menu.add_separator()
        edit_menu.add_command(
            label="Line Up", accelerator="Ctrl+Up", command=self._on_line_up
        )
        edit_menu.add_command(
            label="Line Down", accelerator="Ctrl+Down", command=self._on_line_down
        )
        edit_menu.add_command(
            label="Delete Line", accelerator="Ctrl+Y", command=self._on_delete_line
        )
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # ── Format ──
        format_menu = tb.Menu(menubar, tearoff=False)
        format_menu.add_command(
            label="Bold", accelerator="Ctrl+B", command=lambda: self._wrap_selection("**")
        )
        format_menu.add_command(
            label="Italic", accelerator="Ctrl+I", command=lambda: self._wrap_selection("*")
        )
        format_menu.add_command(
            label="Underline", accelerator="Ctrl+U",
            command=lambda: self._wrap_selection("^^"),
        )
        format_menu.add_command(
            label="Strikethrough", accelerator="Ctrl+D",
            command=lambda: self._wrap_selection("~~"),
        )
        format_menu.add_separator()
        format_menu.add_command(
            label="Superscript", accelerator="Ctrl+Shift+P",
            command=lambda: self._wrap_selection("^"),
        )
        format_menu.add_command(
            label="Subscript", accelerator="Ctrl+Shift+B",
            command=lambda: self._wrap_selection("~"),
        )
        format_menu.add_command(
            label="Inline Code", accelerator="Ctrl+K",
            command=lambda: self._wrap_selection("`"),
        )
        format_menu.add_command(
            label="Mark", accelerator="Ctrl+Shift+M",
            command=lambda: self._wrap_selection("=="),
        )
        format_menu.add_separator()
        format_menu.add_command(
            label="Header ID...", accelerator="Ctrl+H", command=self._on_header_id
        )
        format_menu.add_command(
            label="Header Link...", accelerator="Ctrl+Shift+H",
            command=self._on_header_link,
        )
        format_menu.add_command(
            label="Hyperlink...", accelerator="Ctrl+L", command=self._on_hyperlink
        )
        format_menu.add_command(
            label="Footnote...", accelerator="Ctrl+Shift+U", command=self._on_footnote
        )
        format_menu.add_separator()
        format_menu.add_command(
            label="Language Marker...", accelerator="Ctrl+W",
            command=self._on_language_marker,
        )
        format_menu.add_command(
            label="Language Wrapping...", accelerator="Ctrl+Shift+W",
            command=self._on_language_wrapping,
        )
        format_menu.add_command(
            label="Furigana...", accelerator="Ctrl+Shift+J", command=self._on_furigana
        )
        format_menu.add_command(
            label="Date and Time...", accelerator="Ctrl+Shift+D",
            command=self._on_date_time,
        )
        format_menu.add_command(
            label="Special Mark", accelerator="Ctrl+Shift+L",
            command=self._on_special_mark,
        )
        format_menu.add_separator()
        cjk_menu = tb.Menu(menubar, tearoff=False)
        for code in CJK_CODES:
            cjk_menu.add_command(
                label=code,
                command=lambda c=code: self._insert_text(f"{{:{c}}}"),
            )
        format_menu.add_cascade(label="CJK Codes", menu=cjk_menu)
        emoji_menu = tb.Menu(menubar, tearoff=False)
        for code in EMOJIS:
            emoji_menu.add_command(
                label=f":{code}:",
                command=lambda c=code: self._insert_text(f":{c}:"),
            )
        format_menu.add_cascade(label="Emoji Shortcodes", menu=emoji_menu)
        special_menu = tb.Menu(menubar, tearoff=False)
        for name, code in SPECIAL_SIGNS:
            special_menu.add_command(
                label=f"{code} {name}",
                command=lambda c=code: self._insert_text(c),
            )
        format_menu.add_cascade(label="Special Signs", menu=special_menu)
        format_menu.add_separator()
        format_menu.add_command(
            label="Clear Formatting", accelerator="Ctrl+Shift+F",
            command=self._on_clear_formatting,
        )
        menubar.add_cascade(label="Format", menu=format_menu)

        # ── Paragraph ──
        para_menu = tb.Menu(menubar, tearoff=False)
        for level in range(1, 7):
            para_menu.add_command(
                label=f"Heading {level}",
                accelerator=f"Alt+Ctrl+{level}",
                command=lambda lv=level: self._on_heading(lv),
            )
        para_menu.add_separator()
        para_menu.add_command(
            label="Paragraph", accelerator="Alt+Ctrl+0", command=self._on_paragraph
        )
        para_menu.add_command(
            label="Ordered List", accelerator="Ctrl+G", command=self._on_ordered_list
        )
        para_menu.add_command(
            label="Unordered List", accelerator="Ctrl+Shift+G",
            command=self._on_unordered_list,
        )
        para_menu.add_command(
            label="Definition List...", accelerator="Ctrl+Shift+X",
            command=self._on_definition_list,
        )
        para_menu.add_separator()
        para_menu.add_command(
            label="Code Block...", accelerator="Ctrl+Shift+K",
            command=self._on_code_block,
        )
        para_menu.add_command(
            label="Blockquote", accelerator="Ctrl+Shift+Q", command=self._on_blockquote
        )
        para_menu.add_command(
            label="Table...", accelerator="Ctrl+T", command=self._on_table
        )
        para_menu.add_command(
            label="Image...", accelerator="Ctrl+Shift+I", command=self._on_image
        )
        para_menu.add_separator()
        para_menu.add_command(
            label="Line Break", accelerator="Ctrl+\\", command=self._on_line_break
        )
        para_menu.add_command(
            label="Horizontal Rule", accelerator="Ctrl+_", command=self._on_horizontal_rule
        )
        para_menu.add_separator()
        para_menu.add_command(
            label="Add Indent", accelerator="Tab", command=self._on_add_indent
        )
        para_menu.add_command(
            label="Remove Indent", accelerator="Shift+Tab", command=self._on_remove_indent
        )
        para_menu.add_separator()
        para_menu.add_command(
            label="Comment...", accelerator="Ctrl+M", command=self._on_comment
        )
        para_menu.add_command(
            label="YAML Front Matter...", accelerator="Ctrl+Shift+Y",
            command=self._on_yaml_front_matter,
        )
        menubar.add_cascade(label="Paragraph", menu=para_menu)

        # ── View ──
        view_menu = tb.Menu(menubar, tearoff=False)
        view_menu.add_command(
            label="Toggle Theme", accelerator="Ctrl+Shift+T", command=self._on_toggle_theme
        )
        theme_menu = tb.Menu(menubar, tearoff=False)
        for theme_name in THEMES:
            theme_menu.add_command(
                label=theme_name,
                command=lambda t=theme_name: self._on_change_theme(t),
            )
        view_menu.add_cascade(label="Change Theme", menu=theme_menu)
        view_menu.add_separator()
        view_menu.add_command(
            label="Zoom In", accelerator="Ctrl++", command=self._on_zoom_in
        )
        view_menu.add_command(
            label="Zoom Out", accelerator="Ctrl+-", command=self._on_zoom_out
        )
        view_menu.add_separator()
        view_menu.add_command(
            label="Quick View", accelerator="Ctrl+Alt+V", command=self._on_quick_view
        )
        view_menu.add_command(
            label="Quick View CSS",
            accelerator="Ctrl+Alt+C",
            command=self._on_quick_view_css,
        )
        menubar.add_cascade(label="View", menu=view_menu)

        # ── Help ──
        help_menu = tb.Menu(menubar, tearoff=False)
        help_menu.add_command(
            label="Markdown Guide", command=self._on_help_markdown_guide
        )
        help_menu.add_command(label="About Editor", command=self._on_help_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def _build_panels(self) -> None:
        # ── single, full-width editing panel ──
        editor_frame = tb.Frame(self)
        editor_row = tb.Frame(editor_frame)

        self._line_numbers = tk.Text(
            editor_row,
            width=4,
            font=(self.editor_mono[0], self.editor_font_size - 2, "normal"),
            padx=4,
            pady=8,
            relief=tk.FLAT,
            borderwidth=0,
            takefocus=0,
            cursor="arrow",
            state=tk.DISABLED,
        )
        self._line_numbers.pack(side=tk.LEFT, fill=tk.Y)
        self._line_numbers._tb_no_autostyle = True

        self._editor_vbar = tb.Scrollbar(editor_row, orient=tk.VERTICAL)
        self._editor = tk.Text(
            editor_row,
            font=self.editor_font,
            wrap=tk.WORD,
            undo=True,
            padx=8,
            pady=8,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#ccc",
            yscrollcommand=self._on_editor_scroll,
        )
        self._editor_vbar.config(command=self._editor.yview)
        self._editor_vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._editor.pack(fill=tk.BOTH, expand=True)
        self._editor._tb_no_autostyle = True
        self._editor.configure(
            font=(self.editor_font[0], self.editor_font_size, "normal")
        )
        self._editor.tag_configure(
            "code", font=(self.editor_mono[0], self.editor_font_size - 1, "normal")
        )

        editor_row.pack(fill=tk.BOTH, expand=True)
        editor_frame.pack(fill=tk.BOTH, expand=True)

        self._editor.bind("<<Modified>>", self._on_editor_modified)
        self._editor.bind("<ButtonRelease-1>", self._update_status, add=True)
        self._editor.bind("<KeyPress>", self._update_status)

    def _on_editor_scroll(self, first: str, last: str) -> None:
        """Keep the line-number gutter in sync with the editor."""
        self._editor_vbar.set(first, last)
        self._line_numbers.yview_moveto(first)

    def _build_statusbar(self) -> None:
        self._status_var = tb.StringVar(value="Ln 1, Col 1")
        status = tb.Label(
            self,
            textvariable=self._status_var,
            anchor=tk.E,
            padding=(10, 2),
            font=(self.editor_font[0], STATUS_FONT_SIZE, "normal"),
            bootstyle="inverse-secondary",
        )
        status.pack(side=tk.BOTTOM, fill=tk.X)

    def _bind_shortcuts(self) -> None:
        self.bind_all("<Control-n>", lambda e: self._on_new())
        self.bind_all("<Control-o>", lambda e: self._on_open())
        self.bind_all("<Control-Shift-O>", lambda e: self._on_reopen())
        self.bind_all("<Control-s>", lambda e: self._on_save())
        self.bind_all("<Control-Shift-S>", lambda e: self._on_save_as())
        self.bind_all("<Control-e>", lambda e: self._on_convert())
        self.bind_all("<Control-q>", lambda e: self._on_quit())

        self.bind_all("<Control-z>", lambda e: self._on_undo())
        self.bind_all("<Control-Shift-Z>", lambda e: self._on_redo())
        self.bind_class(
            "Text", "<Control-x>",
            lambda e: self._on_cut() if e.widget == self._editor else None,
        )
        self.bind_class(
            "Text", "<Control-c>",
            lambda e: self._on_copy() if e.widget == self._editor else None,
        )
        self.bind_class(
            "Text", "<Control-v>",
            lambda e: self._on_paste() if e.widget == self._editor else None,
        )
        self.bind_all("<Control-f>", lambda e: self._on_find())
        self.bind_all("<Control-r>", lambda e: self._on_replace())
        self.bind_all("<Control-Shift-R>", lambda e: self._on_replace_all())
        self.bind_all("<Control-a>", lambda e: self._on_select_all())
        self.bind_all("<Control-Shift-A>", lambda e: self._on_remove_selection())
        self.bind_all("<Control-Up>", lambda e: self._on_line_up())
        self.bind_all("<Control-Down>", lambda e: self._on_line_down())
        self.bind_all("<Control-y>", lambda e: self._on_delete_line())

        self.bind_all("<Control-b>", lambda e: self._wrap_selection("**"))
        self.bind_all("<Control-i>", lambda e: self._wrap_selection("*"))
        self.bind_all("<Control-u>", lambda e: self._wrap_selection("^^"))
        self.bind_all("<Control-d>", lambda e: self._wrap_selection("~~"))
        self.bind_all("<Control-Shift-p>", lambda e: self._wrap_selection("^"))
        self.bind_all("<Control-Shift-b>", lambda e: self._wrap_selection("~"))
        self.bind_all("<Control-k>", lambda e: self._wrap_selection("`"))
        self.bind_all("<Control-Shift-m>", lambda e: self._wrap_selection("=="))
        self.bind_all("<Control-h>", lambda e: self._on_header_id())
        self.bind_all("<Control-Shift-H>", lambda e: self._on_header_link())
        self.bind_all("<Control-l>", lambda e: self._on_hyperlink())
        self.bind_all("<Control-Shift-u>", lambda e: self._on_footnote())
        self.bind_all("<Control-w>", lambda e: self._on_language_marker())
        self.bind_all("<Control-Shift-W>", lambda e: self._on_language_wrapping())
        self.bind_all("<Control-Shift-j>", lambda e: self._on_furigana())
        self.bind_all("<Control-Shift-d>", lambda e: self._on_date_time())
        self.bind_all("<Control-Shift-l>", lambda e: self._on_special_mark())
        self.bind_all("<Control-Shift-f>", lambda e: self._on_clear_formatting())

        self.bind_all("<Alt-Control-Key-1>", lambda e: self._on_heading(1))
        self.bind_all("<Alt-Control-Key-2>", lambda e: self._on_heading(2))
        self.bind_all("<Alt-Control-Key-3>", lambda e: self._on_heading(3))
        self.bind_all("<Alt-Control-Key-4>", lambda e: self._on_heading(4))
        self.bind_all("<Alt-Control-Key-5>", lambda e: self._on_heading(5))
        self.bind_all("<Alt-Control-Key-6>", lambda e: self._on_heading(6))
        self.bind_all("<Alt-Control-Key-0>", lambda e: self._on_paragraph())
        self.bind_all("<Control-g>", lambda e: self._on_ordered_list())
        self.bind_all("<Control-Shift-g>", lambda e: self._on_unordered_list())
        self.bind_all("<Control-Shift-x>", lambda e: self._on_definition_list())
        self.bind_all("<Control-Shift-k>", lambda e: self._on_code_block())
        self.bind_all("<Control-Shift-q>", lambda e: self._on_blockquote())
        self.bind_all("<Control-t>", lambda e: self._on_table())
        self.bind_all("<Control-Shift-i>", lambda e: self._on_image())
        self.bind_all("<Control-backslash>", lambda e: self._on_line_break())
        self.bind_all("<Control-underscore>", lambda e: self._on_horizontal_rule())
        self.bind_all("<Tab>", lambda e: self._on_add_indent())
        self.bind_all("<Shift-Tab>", lambda e: self._on_remove_indent())
        self.bind_all("<Control-m>", lambda e: self._on_comment())
        self.bind_all("<Control-Shift-y>", lambda e: self._on_yaml_front_matter())

        self.bind_all("<Control-equal>", lambda e: self._on_zoom_in())
        self.bind_all("<Control-plus>", lambda e: self._on_zoom_in())
        self.bind_all("<Control-minus>", lambda e: self._on_zoom_out())
        self.bind_all("<Control-Shift-t>", lambda e: self._on_toggle_theme())
        self.bind_all("<Control-Alt-v>", lambda e: self._on_quick_view())
        self.bind_all("<Control-Alt-c>", lambda e: self._on_quick_view_css())

    # ── Title bar & status ────────────────────────────────────────────

    def _update_title(self) -> None:
        symbol = "*" if self.is_modified else ""
        name = self.current_file.name if self.current_file else "New File"
        self.title(f"{APP_NAME} - {symbol}{name}")

    def _update_status(self, _event=None) -> None:
        try:
            idx = self._editor.index(tk.INSERT)
            line, col = idx.split(".")
            self._status_var.set(f"Ln {line}, Col {int(col) + 1}")
        except Exception:
            pass

    # ── Change tracking ───────────────────────────────────────────────

    def _on_editor_modified(self, _event=None) -> None:
        if not self._editor.edit_modified():
            return
        self._editor.edit_modified(False)
        self.is_modified = True
        self._update_title()
        self._update_line_numbers()

    def _update_line_numbers(self) -> None:
        self._line_numbers.config(state=tk.NORMAL)
        self._line_numbers.delete("1.0", tk.END)
        total = int(self._editor.index("end-1c").split(".")[0])
        numbers = "\n".join(str(i) for i in range(1, total + 1))
        self._line_numbers.insert("1.0", numbers)
        self._line_numbers.config(state=tk.DISABLED)

    # ── File operations ───────────────────────────────────────────────

    def _check_save(self) -> bool:
        """Ask the user about saving before closing. Returns True to proceed."""
        if not self.is_modified:
            return True
        answer = Messagebox.yesno(
            "Save the opened file?", title="Save changes", parent=self
        )
        if answer == "Yes":
            return self._on_save()
        return True

    def _on_new(self) -> None:
        if not self._check_save():
            return
        self._editor.delete("1.0", tk.END)
        self.current_file = None
        self.is_modified = False
        self._editor.edit_modified(False)
        self._update_title()
        self._update_line_numbers()
        self._editor.focus_set()

    def _on_open(self) -> None:
        if not self._check_save():
            return
        path = filedialog.askopenfilename(
            title="Open file",
            filetypes=[("Markdown files", "*.md *.markdown"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8")
        except Exception as exc:
            Messagebox.show_error(str(exc), title="Open file", parent=self)
            return
        self._editor.delete("1.0", tk.END)
        self._editor.insert("1.0", text)
        self.current_file = Path(path)
        self.is_modified = False
        self._editor.edit_modified(False)
        self._update_title()
        self._update_line_numbers()

    def _on_reopen(self) -> None:
        if not self.current_file:
            return
        if not self._check_save():
            return
        try:
            text = self.current_file.read_text(encoding="utf-8")
        except Exception as exc:
            Messagebox.show_error(str(exc), title="Reopen file", parent=self)
            return
        self._editor.delete("1.0", tk.END)
        self._editor.insert("1.0", text)
        self.is_modified = False
        self._editor.edit_modified(False)
        self._update_title()
        self._update_line_numbers()
        Messagebox.show_info("File reopened!", title="Reopen file", parent=self)

    def _on_save(self) -> bool:
        if self.current_file:
            self._save_to(self.current_file)
            return True
        return self._on_save_as()

    def _save_to(self, path: Path) -> None:
        try:
            path.write_text(self._editor.get("1.0", "end-1c"), encoding="utf-8")
            self.current_file = path
            self.is_modified = False
            self._editor.edit_modified(False)
            self._update_title()
        except Exception as exc:
            Messagebox.show_error(str(exc), title="Save file", parent=self)
            return
        Messagebox.show_info("File saved!", title="Save file", parent=self)

    def _on_save_as(self) -> bool:
        path = filedialog.asksaveasfilename(
            title="Save As",
            defaultextension=".md",
            initialfile=(self.current_file.name if self.current_file else "untitled.md"),
            filetypes=[("Markdown files", "*.md *.markdown"), ("All files", "*.*")],
        )
        if not path:
            return False
        self._save_to(Path(path))
        return True

    def _on_convert(self) -> None:
        choice = Querybox.get_item(
            "Choose the target format:",
            initialvalue="HTML5 file (.html)",
            items=[
                "HTML5 file (.html)",
                "HTML5 file with CSS3 (.html)",
                "Plain text file (.txt)",
                "PDF file (.pdf)",
            ],
            title="Convert",
            parent=self,
        )
        if not choice:
            return
        if choice.startswith("HTML5 file with"):
            ext, ftype, include_css = ".html", [("HTML5 files", "*.html")], True
        elif choice.startswith("HTML5"):
            ext, ftype, include_css = ".html", [("HTML5 files", "*.html")], False
        elif choice.startswith("Plain"):
            ext, ftype, include_css = ".txt", [("Plain text files", "*.txt")], False
        else:
            ext, ftype, include_css = ".pdf", [("PDF files", "*.pdf")], False

        base = self.current_file.name if self.current_file else "document"
        if base.endswith(".md") or base.endswith(".markdown"):
            base = base.rsplit(".", 1)[0]
        path = filedialog.asksaveasfilename(
            title="Convert",
            defaultextension=ext,
            initialfile=base + ext,
            filetypes=ftype,
        )
        if not path:
            return
        try:
            self._perform_convert(Path(path), ext, include_css=include_css)
        except Exception as exc:
            Messagebox.show_error(str(exc), title="Convert", parent=self)
            return
        Messagebox.show_info("Conversion complete!", title="Convert", parent=self)

    def _perform_convert(self, path: Path, ext: str, include_css: bool = False) -> None:
        content = self._editor.get("1.0", "end-1c")
        if ext == ".html":
            html = self.converter.convert(content, include_css=include_css)
            path.write_text(html, encoding="utf-8")
        elif ext == ".txt":
            path.write_text(self._md_to_plain(content), encoding="utf-8")
        else:
            md2pdf_convert(content, str(path))

    def _md_to_plain(self, text: str) -> str:
        """Strip Markdown syntax to produce plain text."""
        text = re.sub(r"^```[^\n]*\n?", "", text, flags=re.M)
        text = re.sub(r"^#+\s?", "", text, flags=re.M)
        text = re.sub(r"^\s*([-*+>])\s+", "", text, flags=re.M)
        text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.M)
        text = re.sub(r"^\s*(\|\s*)+$", "", text, flags=re.M)
        text = re.sub(r"^---\s*$", "", text, flags=re.M)
        text = re.sub(r"^:::+\s*$", "", text, flags=re.M)
        text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
        text = re.sub(r"\{[^}]*\}", "", text)
        text = re.sub(r"[*_~^`=]{1,2}", "", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() + "\n"

    def _on_quit(self) -> None:
        if self._check_save():
            self.destroy()

    # ── Edit operations ───────────────────────────────────────────────

    def _on_undo(self) -> None:
        if self._editor.edit_modified():
            self._editor.edit_modified(False)
        try:
            self._editor.edit_undo()
        except tk.TclError:
            pass

    def _on_redo(self) -> None:
        try:
            self._editor.edit_redo()
        except tk.TclError:
            pass

    def _on_cut(self) -> None:
        self._editor.event_generate("<<Cut>>")

    def _on_copy(self) -> None:
        self._editor.event_generate("<<Copy>>")

    def _on_paste(self) -> None:
        self._editor.event_generate("<<Paste>>")

    def _on_select_all(self) -> None:
        self._editor.tag_add(tk.SEL, "1.0", tk.END)
        self._editor.mark_set(tk.INSERT, "1.0")
        self._editor.see(tk.INSERT)

    def _on_remove_selection(self) -> None:
        self._editor.tag_remove(tk.SEL, "1.0", tk.END)

    def _on_line_up(self) -> None:
        cur = self._editor.index(tk.INSERT)
        line = int(cur.split(".")[0])
        if line <= 1:
            return
        cur_text = self._get_current_line_text()
        prev_text = self._editor.get(f"{line - 1}.0", f"{line - 1}.end")
        self._editor.delete(f"{line - 1}.0", f"{line}.end")
        self._editor.insert(f"{line - 1}.0", f"{cur_text}\n{prev_text}")
        self._editor.mark_set(tk.INSERT, f"{line - 1}.0")

    def _on_line_down(self) -> None:
        cur = self._editor.index(tk.INSERT)
        line = int(cur.split(".")[0])
        total = int(self._editor.index("end-1c").split(".")[0])
        if line >= total:
            return
        cur_text = self._get_current_line_text()
        next_text = self._editor.get(f"{line + 1}.0", f"{line + 1}.end")
        self._editor.delete(f"{line}.0", f"{line + 1}.end")
        self._editor.insert(f"{line}.0", f"{next_text}\n{cur_text}")
        self._editor.mark_set(tk.INSERT, f"{line + 1}.0")

    def _on_delete_line(self) -> None:
        cur = self._editor.index(tk.INSERT)
        line = int(cur.split(".")[0])
        self._editor.delete(f"{line}.0", f"{line + 1}.0")
        self._editor.mark_set(tk.INSERT, f"{line}.0")

    def _on_find(self) -> None:
        dlg = FindDialog(self, self._editor)
        dlg.callback = lambda *a, **k: None
        dlg.grab_set()

    def _on_replace(self) -> None:
        dlg = ReplaceDialog(self, self._editor)
        dlg.callback = lambda *a, **k: None
        dlg.grab_set()

    def _on_replace_all(self) -> None:
        dlg = ReplaceDialog(self, self._editor)
        dlg.callback = lambda *a, **k: None
        dlg.grab_set()

    # ── Format operations ─────────────────────────────────────────────

    def _insert_text(self, text: str) -> None:
        self._editor.insert(tk.INSERT, text)
        self._editor.focus_set()

    def _wrap_selection(self, wrapper: str) -> None:
        try:
            sel_start = self._editor.index(tk.SEL_FIRST)
            sel_end = self._editor.index(tk.SEL_LAST)
            has_selection = True
        except tk.TclError:
            has_selection = False

        if has_selection:
            text = self._editor.get(sel_start, sel_end)
            self._editor.delete(sel_start, sel_end)
            self._editor.insert(sel_start, f"{wrapper}{text}{wrapper}")
            self._editor.tag_add(tk.SEL, sel_start, f"{sel_start}+{len(wrapper + text + wrapper)}c")
            self._editor.mark_set(tk.INSERT, f"{sel_start}+{len(wrapper)}c")
        else:
            self._editor.insert(tk.INSERT, f"{wrapper}{wrapper}")
            self._editor.mark_set(
                tk.INSERT, f"insert-{len(wrapper)}c"
            )
        self._editor.focus_set()

    def _on_header_id(self) -> None:
        line = self._get_current_line_text()
        if not line.strip():
            return
        hid = Querybox.get_string("Enter the header ID (without #):", title="Header ID",
                                  parent=self)
        if not hid:
            return
        hid = hid.strip().lstrip("#")
        self._replace_current_line(f"{line.rstrip()} {{#{hid}}}")

    def _on_header_link(self) -> None:
        dlg = HeaderLinkDialog(self)
        dlg.callback = lambda text: self._insert_text(text)
        dlg.grab_set()

    def _on_hyperlink(self) -> None:
        try:
            sel_start = self._editor.index(tk.SEL_FIRST)
            sel_end = self._editor.index(tk.SEL_LAST)
            selected = self._editor.get(sel_start, sel_end)
        except tk.TclError:
            selected = ""
        url = Querybox.get_string("Enter the URL:", title="Hyperlink", parent=self)
        if not url:
            return
        text = selected or Querybox.get_string(
            "Enter the link text:", title="Hyperlink", parent=self
        ) or url
        if selected:
            self._editor.delete(sel_start, sel_end)
            self._editor.insert(sel_start, f"[{text}]({url})")
        else:
            self._editor.insert(tk.INSERT, f"[{text}]({url})")
        self._editor.focus_set()

    def _on_footnote(self) -> None:
        dlg = FootnoteDialog(self)
        dlg.callback = self._insert_footnote
        dlg.grab_set()

    def _insert_footnote(self, ref: str, definition: str) -> None:
        self._editor.insert(tk.INSERT, f"[^{ref}]")
        if definition:
            self._editor.insert(tk.END, f"\n\n[^{ref}]: {definition}")
        self._editor.focus_set()

    def _on_language_marker(self) -> None:
        lang = Querybox.get_string(
            "Enter a BCP 47 language tag (e.g. de):", title="Language Marker",
            parent=self,
        )
        if not lang:
            return
        lang = lang.strip()
        line = self._get_current_line_text()
        self._replace_current_line(f"{{:{lang}}} {line}")
        self._editor.focus_set()

    def _on_language_wrapping(self) -> None:
        lang = Querybox.get_string(
            "Enter a BCP 47 language tag (e.g. fr):", title="Language Wrapping",
            parent=self,
        )
        if not lang:
            return
        lang = lang.strip()
        try:
            sel_start = self._editor.index(tk.SEL_FIRST)
            sel_end = self._editor.index(tk.SEL_LAST)
        except tk.TclError:
            sel_start = sel_end = None
        if sel_start:
            text = self._editor.get(sel_start, sel_end)
            self._editor.delete(sel_start, sel_end)
            self._editor.insert(sel_start, f"{{:{lang}}}{text}{{:}}")
        else:
            self._editor.insert(
                tk.INSERT, f"{{:{lang}}}{{:}}"
            )
        self._editor.focus_set()

    def _on_furigana(self) -> None:
        dlg = FuriganaDialog(self)
        dlg.callback = self._insert_text
        dlg.grab_set()

    def _on_date_time(self) -> None:
        dlg = DateTimeDialog(self)
        dlg.callback = self._insert_text
        dlg.grab_set()

    def _on_special_mark(self) -> None:
        self._editor.insert(tk.INSERT, "\\")
        self._editor.focus_set()

    def _on_clear_formatting(self) -> None:
        text = self._editor.get("1.0", "end-1c")
        cleaned = self._md_to_plain(text)
        self._editor.delete("1.0", tk.END)
        self._editor.insert("1.0", cleaned)

    # ── Paragraph operations ──────────────────────────────────────────

    def _get_current_line_text(self) -> str:
        cur = self._editor.index(tk.INSERT)
        line = int(cur.split(".")[0])
        return self._editor.get(f"{line}.0", f"{line}.end")

    def _replace_current_line(self, new_text: str) -> None:
        cur = self._editor.index(tk.INSERT)
        line = int(cur.split(".")[0])
        self._editor.delete(f"{line}.0", f"{line}.end")
        self._editor.insert(f"{line}.0", new_text)
        self._editor.mark_set(tk.INSERT, f"{line}.0")

    def _add_blank_line_before_if_needed(self) -> None:
        cur = self._editor.index(tk.INSERT)
        line = int(cur.split(".")[0])
        if line <= 1:
            return
        prev = self._editor.get(f"{line - 1}.0", f"{line - 1}.end")
        if prev.strip() != "":
            self._editor.insert(f"{line}.0", "\n")

    def _on_heading(self, level: int) -> None:
        text = self._get_current_line_text()
        text = re.sub(r"^#{1,6}\s*", "", text)
        self._add_blank_line_before_if_needed()
        self._replace_current_line(f"{'#' * level} {text}")

    def _on_paragraph(self) -> None:
        text = self._get_current_line_text()
        text = re.sub(r"^#{1,6}\s*", "", text)
        self._add_blank_line_before_if_needed()
        self._replace_current_line(text)

    def _on_ordered_list(self) -> None:
        text = self._get_current_line_text()
        text = re.sub(r"^(\d+\.|\*|-|>)\s*", "", text)
        self._add_blank_line_before_if_needed()
        self._replace_current_line(f"1. {text}")

    def _on_unordered_list(self) -> None:
        text = self._get_current_line_text()
        text = re.sub(r"^(\d+\.|\*|-|>)\s*", "", text)
        self._add_blank_line_before_if_needed()
        self._replace_current_line(f"* {text}")

    def _on_definition_list(self) -> None:
        dlg = DefinitionListDialog(self)
        dlg.callback = self._insert_block
        dlg.grab_set()

    def _on_code_block(self) -> None:
        lang = Querybox.get_string(
            "Enter the programming language (optional):", title="Code Block",
            parent=self,
        ) or ""
        lang = lang.strip()
        text = self._get_current_line_text()
        self._add_blank_line_before_if_needed()
        self._replace_current_line(
            f"```{lang}\n{text}\n```"
        )

    def _on_blockquote(self) -> None:
        text = self._get_current_line_text()
        text = re.sub(r"^>\s*", "", text)
        self._add_blank_line_before_if_needed()
        self._replace_current_line(f"> {text}")

    def _on_table(self) -> None:
        dlg = TableDialog(self)
        dlg.callback = self._insert_block
        dlg.grab_set()

    def _on_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose an image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.svg *.webp"),
                       ("All files", "*.*")],
        )
        if not path:
            return
        alt = Querybox.get_string("Enter the Alt text:", title="Image", parent=self) or ""
        title = Querybox.get_string(
            "Enter an Optional title (or leave empty):", title="Image", parent=self
        ) or ""
        alt = alt.strip()
        title = title.strip()
        if title:
            markdown = f"![{alt}]({path} \"{title}\")"
        else:
            markdown = f"![{alt}]({path})"
        self._add_blank_line_before_if_needed()
        self._insert_block(markdown)

    def _on_line_break(self) -> None:
        self._editor.insert(tk.INSERT, "  \n")
        self._editor.focus_set()

    def _on_horizontal_rule(self) -> None:
        self._insert_block("***")

    def _on_add_indent(self) -> None:
        cur = self._editor.index(tk.INSERT)
        line = int(cur.split(".")[0])
        self._editor.insert(f"{line}.0", "  ")
        self._editor.mark_set(tk.INSERT, f"{line}.2")

    def _on_remove_indent(self) -> None:
        cur = self._editor.index(tk.INSERT)
        line = int(cur.split(".")[0])
        text = self._editor.get(f"{line}.0", f"{line}.end")
        if text.startswith("  "):
            self._editor.delete(f"{line}.0", f"{line}.2")
        elif text.startswith(" "):
            self._editor.delete(f"{line}.0", f"{line}.1")

    def _on_comment(self) -> None:
        comment = Querybox.get_string(
            "Enter the comment text:", title="Comment", parent=self
        )
        if comment is None:
            return
        comment = comment.strip()
        self._insert_block(f"[{comment}]: #")

    def _on_yaml_front_matter(self) -> None:
        dlg = YAMLFrontMatterDialog(self)
        dlg.callback = self._insert_yaml_front_matter
        dlg.grab_set()

    def _insert_yaml_front_matter(self, block: str) -> None:
        text = self._editor.get("1.0", "end-1c")
        if text.startswith("---"):
            Messagebox.show_warning(
                "The document already has a YAML Front Matter block.",
                title="YAML Front Matter",
                parent=self,
            )
            return
        self._editor.insert("1.0", block + "\n\n")
        self._editor.focus_set()

    def _insert_block(self, text: str) -> None:
        self._add_blank_line_before_if_needed()
        self._editor.insert(tk.INSERT, text + "\n")
        self._editor.focus_set()

    # ── View operations ───────────────────────────────────────────────

    def _on_toggle_theme(self) -> None:
        current = self.style.theme_use()
        base = current.rsplit("-", 1)[0]
        if current.endswith("-light"):
            new = f"{base}-dark"
        elif current.endswith("-dark"):
            new = f"{base}-light"
        else:
            new = "one-dark" if current != "one-dark" else "one-light"
        self._apply_theme(new)

    def _on_change_theme(self, name: str) -> None:
        self._apply_theme(name)

    def _apply_theme(self, name: str) -> None:
        if name in THEMES:
            self.style.theme_use(name)
            save_theme(name)

    def _on_zoom_in(self) -> None:
        self._adjust_editor_font(ZOOM_STEP)

    def _on_zoom_out(self) -> None:
        self._adjust_editor_font(-ZOOM_STEP)

    def _adjust_editor_font(self, delta: int) -> None:
        new_size = max(8, self.editor_font_size + delta)
        if new_size == self.editor_font_size:
            return
        self.editor_font_size = new_size
        self._editor.configure(font=(self.editor_font[0], new_size, "normal"))
        self._editor.tag_configure(
            "code", font=(self.editor_mono[0], new_size - 1, "normal")
        )
        self._line_numbers.configure(
            font=(self.editor_mono[0], new_size - 2, "normal")
        )
        self._update_line_numbers()

    def _on_quick_view(self) -> None:
        self._quick_view(include_css=False)

    def _on_quick_view_css(self) -> None:
        self._quick_view(include_css=True)

    def _quick_view(self, include_css: bool) -> None:
        cache_dir = ensure_cache_dir()
        html_path = cache_dir / TEMP_HTML
        content = self._editor.get("1.0", "end-1c")
        try:
            html = self.converter.convert(content, include_css=include_css)
            html_path.write_text(html, encoding="utf-8")
        except Exception as exc:
            Messagebox.show_error(str(exc), title="Quick View", parent=self)
            return
        webbrowser.open(html_path.as_uri())

    # ── Help operations ───────────────────────────────────────────────

    def _on_help_markdown_guide(self) -> None:
        webbrowser.open("https://www.markdownguide.org/")

    def _on_help_about(self) -> None:
        about = tb.Toplevel(self)
        about.title("About")
        about.resizable(False, False)
        about.transient(self)
        icon = resource_path(os.path.join("images", "mark_editor.png"))
        if os.path.exists(icon):
            try:
                photo = tk.PhotoImage(file=icon)
                about.iconphoto(True, photo)
            except Exception:
                pass
        tb.Label(
            about,
            text=f"{APP_NAME}, version {VERSION} ({RELEASE})",
            font=self.interface_font,
            padding=(24, 18),
        ).pack()
        tb.Button(about, text="Close", bootstyle="secondary",
                  command=about.destroy).pack(pady=(0, 14))
        about.grab_set()


# ═══════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════


def main() -> None:
    app = MarkEditor()
    app.geometry("1100x700")
    app.mainloop()


if __name__ == "__main__":
    main()
