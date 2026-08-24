"""Mark Editor — a simple Markdown editor.

The editor is written as a single Python 3 file using Tkinter and
CustomTkinter. It uses the markdown2html5-base library to convert Markdown
into HTML5 for export and for the Quick view in the browser, and
markdown2pdf-base to export documents as PDF (via pandoc + xelatex).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tkinter as tk
import webbrowser
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from markdown2html5_base import MarkdownToHTML
from markdown2pdf_base import convert as md2pdf_convert

# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

APP_NAME = "Mark Editor"
VERSION = "0.5.0"
RELEASE = "2026.08"

CONFIG_DIR = Path.home() / ".config" / "mark_editor"
THEME_FILE = CONFIG_DIR / "theme.json"

CACHE_DIR = Path.home() / ".cache" / "mark_edit"
TEMP_MD = "~temp.md"
TEMP_HTML = "temp.html"

# Appearance modes supported by CustomTkinter ("light" / "dark").
THEMES: tuple[str, ...] = ("light", "dark")

DEFAULT_THEME = "light"

# CustomTkinter colour theme files used for each appearance mode
# (bundled under themes/, generated from the official palettes).
COLOR_THEMES: dict[str, str] = {
    "light": "themes/mark-light.json",
    "dark": "themes/mark-dark.json",
}

BUILT_IN_COLOR_THEMES: dict[str, str] = {
    "light": "blue",
    "dark": "dark-blue",
}

# Colours of the plain Tk editor widgets per appearance mode.
EDITOR_COLORS: dict[str, dict[str, str]] = {
    "Light": {
        "bg": "#ffffff",
        "fg": "#0f172a",
        "gutter_bg": "#eef2f7",
        "gutter_fg": "#64748b",
        "insert": "#0f172a",
        "find_bg": "#fff3cd",
        "find_fg": "#1f2937",
        "border": "#cbd5e1",
    },
    "Dark": {
        "bg": "#14181f",
        "fg": "#dee7f5",
        "gutter_bg": "#10141b",
        "gutter_fg": "#66748c",
        "insert": "#dee7f5",
        "find_bg": "#2f4a78",
        "find_fg": "#f2f6ff",
        "border": "#2e3746",
    },
}

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

# Fixed font families per category.
FONT_FAMILIES: dict[str, str] = {
    "sans": "Noto Sans",  # for interface, menus, dialog windows
    "mono": "Noto Sans Mono",  # for editor, status bar
    "symbola": "Symbola",
    "cjk_ja": "Noto Sans Mono CJK JP",  # for {:ja} language marker
    "cjk_cn": "Noto Sans Mono CJK SC",  # for {:zh-Hans} or {:zh-CN} or {:zh-Hans-CN} language marker
    "cjk_tw": "Noto Sans Mono CJK TC",  # for {:zh-TW} or {:zh-Hant-TW} language marker
    "cjk_hk": "Noto Sans Mono CJK HK",  # for {:zh-HK} or {:zh-Hant-HK} language marker
    "cjk_kr": "Noto Sans Mono CJK KR",  # for {:ko} or {:ko-KR} language marker
}

# {:lang} markers that switch editor text to a CJK family.
CJK_FONT_TAGS: dict[str, str] = {
    "ja": "cjk_ja",
    "zh-Hans": "cjk_cn",
    "zh-CN": "cjk_cn",
    "zh-Hans-CN": "cjk_cn",
    "zh-TW": "cjk_tw",
    "zh-Hant-TW": "cjk_tw",
    "zh-HK": "cjk_hk",
    "zh-Hant-HK": "cjk_hk",
    "ko": "cjk_kr",
    "ko-KR": "cjk_kr",
}

# Text-widget tag names derived from CJK_FONT_TAGS.
CJK_TAG_KEYS = tuple(sorted(set(CJK_FONT_TAGS.values())))

INTERFACE_FONT_SIZE = 14
STATUS_FONT_SIZE = 16
MENU_FONT_SIZE = 12
EDITOR_FONT_SIZE = 13
ZOOM_STEP = 2


# ═══════════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════════


def resource_path(relative: str) -> str:
    """Return an absolute path for a bundled resource (PyInstaller aware)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def apply_color_theme(mode: str) -> None:
    """Load the colour theme for the given appearance mode.

    Must be called strictly before the main window (ctk.CTk) is created;
    widgets then pick up the colours automatically at creation time.
    Falls back to built-in CustomTkinter themes when the bundled files
    are missing.
    """
    path = resource_path(COLOR_THEMES[mode])
    if os.path.exists(path):
        ctk.set_default_color_theme(path)
    else:
        ctk.set_default_color_theme(BUILT_IN_COLOR_THEMES[mode])


def load_theme() -> str:
    """Load the saved appearance mode from ~/.config/mark_editor/theme.json."""
    try:
        data = json.loads(THEME_FILE.read_text(encoding="utf-8"))
        name = str(data.get("mode", DEFAULT_THEME)).lower()
        if name in THEMES:
            return name
    except Exception:
        pass
    return DEFAULT_THEME


def save_theme(name: str) -> None:
    """Save the current appearance mode to ~/.config/mark_editor/theme.json."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        THEME_FILE.write_text(json.dumps({"mode": name}, indent=2), encoding="utf-8")
    except Exception:
        pass


def current_mode() -> str:
    """Return the active appearance mode ('Light' or 'Dark')."""
    mode = ctk.get_appearance_mode()
    return mode if mode in EDITOR_COLORS else "Light"


def editor_colors() -> dict[str, str]:
    """Return the editor widget colours for the active appearance mode."""
    return EDITOR_COLORS[current_mode()]


def menu_colors() -> dict[str, str]:
    """Return Tk menu colours matching the active CustomTkinter theme."""
    i = 1 if current_mode() == "Dark" else 0
    theme = ctk.ThemeManager.theme
    return {
        "background": theme["DropdownMenu"]["fg_color"][i],
        "foreground": theme["DropdownMenu"]["text_color"][i],
        "activebackground": theme["CTkButton"]["fg_color"][i],
        "activeforeground": "#ffffff",
    }


def ensure_cache_dir() -> Path:
    """Create and return ~/.cache/mark_edit."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


_dialog_font_cache: tuple | None = None


def dialog_font() -> tuple:
    """Return the plain (unscaled) font used across dialog widgets."""
    global _dialog_font_cache
    if _dialog_font_cache is None:
        _dialog_font_cache = ("Noto Sans", 16)
    return _dialog_font_cache


def ask_string(prompt: str, title: str) -> str | None:
    """Show a themed input dialog; return the entered string or None."""
    dialog = ctk.CTkInputDialog(title=title, text=prompt, font=dialog_font())
    result = dialog.get_input()
    if isinstance(result, tuple):
        result = result[0]
    result = (result or "").strip()
    return result or None


_zenity_cache: bool | None = None


def zenity_available() -> bool:
    """Return True if the zenity (GTK) file chooser is usable."""
    global _zenity_cache
    if _zenity_cache is None:
        _zenity_cache = (
            sys.platform.startswith("linux") and shutil.which("zenity") is not None
        )
    return _zenity_cache


def _run_zenity(args: list[str]) -> str | None:
    """Run zenity and return its first stdout line, or None on cancel."""
    try:
        proc = subprocess.run(
            ["zenity", *args], capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return proc.stdout.strip().splitlines()[0]


def _zenity_filter_args(
    filetypes: Sequence[tuple[str, str]] | None,
) -> list[str]:
    """Translate tkinter-style filetypes into zenity --file-filter args."""
    args: list[str] = []
    for label, patterns in filetypes or []:
        exts = [p for p in str(patterns).split() if "*" in p and p not in ("*", "*.*")]
        if exts:
            args += ["--file-filter", f"{label} | {' '.join(exts)}"]
    return args


def ask_open_path(
    title: str,
    filetypes: Sequence[tuple[str, str]] | None = None,
) -> str:
    """Open a GTK file chooser via zenity, falling back to tkinter."""
    if zenity_available():
        out = _run_zenity(
            ["--file-selection", f"--title={title}", *_zenity_filter_args(filetypes)]
        )
        return out or ""
    return filedialog.askopenfilename(title=title, filetypes=list(filetypes or []))


def ask_save_path(
    title: str,
    defaultextension: str = "",
    initialfile: str = "",
    filetypes: Sequence[tuple[str, str]] | None = None,
) -> str:
    """Open a GTK save chooser via zenity, falling back to tkinter."""
    if zenity_available():
        out = _run_zenity(
            [
                "--file-selection",
                "--save",
                "--confirm-overwrite",
                f"--title={title}",
                f"--filename={initialfile}",
                *_zenity_filter_args(filetypes),
            ]
        )
        if out:
            if defaultextension and not Path(out).suffix:
                out += defaultextension
            return out
        return ""
    kwargs = dict(
        title=title, defaultextension=defaultextension, filetypes=list(filetypes or [])
    )
    if initialfile:
        kwargs["initialfile"] = initialfile
    return filedialog.asksaveasfilename(**kwargs)


class DLabel(ctk.CTkLabel):
    """CTkLabel with the fixed dialog font."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, font=dialog_font(), **kwargs)


class DButton(ctk.CTkButton):
    """CTkButton with the fixed dialog font."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, font=dialog_font(), **kwargs)


class DEntry(ctk.CTkEntry):
    """CTkEntry with the fixed dialog font."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, font=dialog_font(), **kwargs)


class DCheckBox(ctk.CTkCheckBox):
    """CTkCheckBox with the fixed dialog font."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, font=dialog_font(), **kwargs)


class DRadioButton(ctk.CTkRadioButton):
    """CTkRadioButton with the fixed dialog font."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, font=dialog_font(), **kwargs)


class DOptionMenu(ctk.CTkOptionMenu):
    """CTkOptionMenu with the fixed dialog font and dropdown font."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(
            master, font=dialog_font(), dropdown_font=dialog_font(), **kwargs
        )


# ═══════════════════════════════════════════════════════════════════════
# Dialog classes
# ═══════════════════════════════════════════════════════════════════════


class ModalDialog(ctk.CTkToplevel):
    """Base class for modal dialogs."""

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.resizable(False, False)
        self.transient(parent)
        self.bind("<Escape>", lambda e: self.destroy())

    def grab_set(self) -> None:
        """Grab input once the window has become viewable."""
        try:
            self.wait_visibility()
            super().grab_set()
        except tk.TclError:
            pass


class ChoiceDialog(ModalDialog):
    """Dialog that lets the user pick one item from a list."""

    def __init__(self, parent, prompt: str, items: list[str], initial: str) -> None:
        super().__init__(parent)
        self.title("Select")
        self.result: str | None = None

        DLabel(self, text=prompt).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 4)
        )
        self.choice_var = tk.StringVar(value=initial)
        DOptionMenu(self, values=items, variable=self.choice_var, width=260).grid(
            row=1, column=0, columnspan=2, padx=12, pady=6
        )

        btn = ctk.CTkFrame(self, fg_color="transparent")
        btn.grid(row=2, column=0, columnspan=2, pady=(4, 12))
        DButton(btn, text="OK", width=90, command=self._confirm).pack(
            side=tk.LEFT, padx=6
        )
        DButton(btn, text="Cancel", width=90, command=self.destroy).pack(
            side=tk.LEFT, padx=6
        )

        self.bind("<Return>", lambda e: self._confirm())

    def _confirm(self) -> None:
        self.result = self.choice_var.get()
        self.destroy()


class FindDialog(ModalDialog):
    """Simple find dialog with regex support."""

    def __init__(self, parent: tk.Tk, text_widget: tk.Text) -> None:
        super().__init__(parent)
        self.title("Find")
        self.text = text_widget
        self.use_regex = tk.BooleanVar(value=False)

        DLabel(self, text="Find:").grid(row=0, column=0, sticky="e", padx=8, pady=6)
        self.find_var = tk.StringVar()
        self.entry = DEntry(self, textvariable=self.find_var, width=240)
        self.entry.grid(row=0, column=1, columnspan=2, padx=4, pady=6)
        self.entry.focus_set()

        DCheckBox(self, text="Use regex", variable=self.use_regex).grid(
            row=1, column=1, columnspan=2, sticky="w", padx=4
        )

        btn = ctk.CTkFrame(self, fg_color="transparent")
        btn.grid(row=2, column=0, columnspan=3, pady=8)
        DButton(btn, text="Find Next", command=self.find_next).pack(
            side=tk.LEFT, padx=4
        )
        DButton(btn, text="Close", command=self.destroy).pack(side=tk.LEFT, padx=4)

        self.bind("<Return>", lambda e: self.find_next())

    def _get_pattern(self) -> re.Pattern | None:
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

    def _search_from(self, pattern: re.Pattern, start: str) -> str | None:
        text = self.text.get("1.0", tk.END)
        start_pos = self.text.index(start)
        offset = self._index_to_offset(start_pos, text)
        match = pattern.search(text, offset)
        if not match:
            return None
        pos = self._offset_to_index(match.start(), text)
        end = self._offset_to_index(match.end(), text)
        self.text.tag_add("find", pos, end)
        colors = editor_colors()
        self.text.tag_configure(
            "find", background=colors["find_bg"], foreground=colors["find_fg"]
        )
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


class ReplaceDialog(ModalDialog):
    """Replace dialog with manual control and a 'Replace All' button."""

    def __init__(self, parent: tk.Tk, text_widget: tk.Text) -> None:
        super().__init__(parent)
        self.title("Replace")
        self.text = text_widget
        self.use_regex = tk.BooleanVar(value=False)

        DLabel(self, text="Find:").grid(row=0, column=0, sticky="e", padx=8, pady=6)
        self.find_var = tk.StringVar()
        DEntry(self, textvariable=self.find_var, width=240).grid(
            row=0, column=1, columnspan=2, padx=4, pady=6
        )

        DLabel(self, text="Replace:").grid(row=1, column=0, sticky="e", padx=8, pady=6)
        self.replace_var = tk.StringVar()
        DEntry(self, textvariable=self.replace_var, width=240).grid(
            row=1, column=1, columnspan=2, padx=4, pady=6
        )

        DCheckBox(self, text="Use regex", variable=self.use_regex).grid(
            row=2, column=1, columnspan=2, sticky="w", padx=4
        )

        btn = ctk.CTkFrame(self, fg_color="transparent")
        btn.grid(row=3, column=0, columnspan=3, pady=8)
        DButton(btn, text="Replace", command=self.replace_one).pack(
            side=tk.LEFT, padx=3
        )
        DButton(btn, text="Replace All", command=self.replace_all).pack(
            side=tk.LEFT, padx=3
        )
        DButton(btn, text="Find Next", command=self.find_next).pack(
            side=tk.LEFT, padx=3
        )
        DButton(btn, text="Close", command=self.destroy).pack(side=tk.LEFT, padx=3)

        self.bind("<Return>", lambda e: self.replace_one())

    def _get_pattern(self) -> re.Pattern | None:
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

    def _find_from(self, pattern: re.Pattern, start: str) -> str | None:
        content = self.text.get("1.0", tk.END)
        offset = self._index_to_offset(start, content)
        match = pattern.search(content, offset)
        if not match:
            return None
        pos = self._offset_to_index(match.start(), content)
        end = self._offset_to_index(match.end(), content)
        self.text.tag_add("find", pos, end)
        colors = editor_colors()
        self.text.tag_configure(
            "find", background=colors["find_bg"], foreground=colors["find_fg"]
        )
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


class TableDialog(ModalDialog):
    """Dialog to create a Markdown table with optional footer."""

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("Insert Table")
        self.cols_var = tk.StringVar(value="3")
        self.rows_var = tk.StringVar(value="3")
        self.footer_var = tk.BooleanVar(value=True)

        DLabel(self, text="Columns:").grid(row=0, column=0, sticky="e", padx=8, pady=6)
        DOptionMenu(
            self,
            values=[str(i) for i in range(1, 21)],
            variable=self.cols_var,
            width=90,
        ).grid(row=0, column=1, padx=4, pady=6)

        DLabel(self, text="Rows:").grid(row=1, column=0, sticky="e", padx=8, pady=6)
        DOptionMenu(
            self,
            values=[str(i) for i in range(1, 51)],
            variable=self.rows_var,
            width=90,
        ).grid(row=1, column=1, padx=4, pady=6)

        DCheckBox(self, text="Add footer", variable=self.footer_var).grid(
            row=2, column=0, columnspan=2, padx=8, pady=4
        )

        btn = ctk.CTkFrame(self, fg_color="transparent")
        btn.grid(row=3, column=0, columnspan=2, pady=8)
        DButton(btn, text="Insert", command=self._insert).pack(side=tk.LEFT, padx=4)
        DButton(btn, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=4)

        self.bind("<Return>", lambda e: self._insert())

    def _insert(self) -> None:
        cols = int(self.cols_var.get())
        rows = int(self.rows_var.get())
        use_footer = self.footer_var.get()

        header = "| " + " | ".join(f"Header {i + 1}" for i in range(cols)) + " |"
        align = "| " + " | ".join(":---:" for _ in range(cols)) + " |"
        lines = ["", header, align]
        for r in range(rows):
            lines.append(
                "| " + " | ".join(f"Cell {r + 1}-{c + 1}" for c in range(cols)) + " |"
            )
        if use_footer:
            lines.append("| " + " | ".join("=" * 8 for _ in range(cols)) + " |")
            lines.append(
                "| " + " | ".join(f"Footer {c + 1}" for c in range(cols)) + " |"
            )
        self.callback("\n".join(lines))
        self.destroy()


class FuriganaDialog(ModalDialog):
    """Dialog to insert a ruby annotation (furigana)."""

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("Furigana (Ruby Annotation)")

        DLabel(self, text="Kanji / Text:").grid(
            row=0, column=0, sticky="e", padx=8, pady=6
        )
        self.kanji_var = tk.StringVar()
        DEntry(self, textvariable=self.kanji_var, width=240).grid(
            row=0, column=1, padx=4, pady=6
        )

        DLabel(self, text="Reading (ruby):").grid(
            row=1, column=0, sticky="e", padx=8, pady=6
        )
        self.reading_var = tk.StringVar()
        DEntry(self, textvariable=self.reading_var, width=240).grid(
            row=1, column=1, padx=4, pady=6
        )

        btn = ctk.CTkFrame(self, fg_color="transparent")
        btn.grid(row=2, column=0, columnspan=2, pady=8)
        DButton(btn, text="Insert", command=self._insert).pack(side=tk.LEFT, padx=4)
        DButton(btn, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=4)

        self.bind("<Return>", lambda e: self._insert())

    def _insert(self) -> None:
        kanji = self.kanji_var.get().strip()
        reading = self.reading_var.get().strip()
        if kanji and reading:
            self.callback(f"{{{kanji} | {reading}}}")
        self.destroy()


class HeaderLinkDialog(ModalDialog):
    """Dialog to insert a link to a header with ID."""

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("Insert Header Link")

        DLabel(self, text="Header ID:").grid(
            row=0, column=0, sticky="e", padx=8, pady=6
        )
        self.id_var = tk.StringVar()
        DEntry(self, textvariable=self.id_var, width=240).grid(
            row=0, column=1, padx=4, pady=6
        )

        DLabel(self, text="Link text:").grid(
            row=1, column=0, sticky="e", padx=8, pady=6
        )
        self.text_var = tk.StringVar()
        DEntry(self, textvariable=self.text_var, width=240).grid(
            row=1, column=1, padx=4, pady=6
        )

        btn = ctk.CTkFrame(self, fg_color="transparent")
        btn.grid(row=2, column=0, columnspan=2, pady=8)
        DButton(btn, text="Insert", command=self._insert).pack(side=tk.LEFT, padx=4)
        DButton(btn, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=4)

        self.bind("<Return>", lambda e: self._insert())

    def _insert(self) -> None:
        hid = self.id_var.get().strip()
        text = self.text_var.get().strip() or hid
        if hid:
            self.callback(f"[{text}](#{hid})")
        self.destroy()


class FootnoteDialog(ModalDialog):
    """Dialog to create a footnote reference and its definition."""

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("Insert Footnote")

        DLabel(self, text="Reference / Name:").grid(
            row=0, column=0, sticky="e", padx=8, pady=6
        )
        self.ref_var = tk.StringVar()
        DEntry(self, textvariable=self.ref_var, width=240).grid(
            row=0, column=1, padx=4, pady=6
        )

        DLabel(self, text="Definition:").grid(
            row=1, column=0, sticky="e", padx=8, pady=6
        )
        self.def_var = tk.StringVar()
        DEntry(self, textvariable=self.def_var, width=240).grid(
            row=1, column=1, padx=4, pady=6
        )

        btn = ctk.CTkFrame(self, fg_color="transparent")
        btn.grid(row=2, column=0, columnspan=2, pady=8)
        DButton(btn, text="Insert", command=self._insert).pack(side=tk.LEFT, padx=4)
        DButton(btn, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=4)

        self.bind("<Return>", lambda e: self._insert())

    def _insert(self) -> None:
        ref = self.ref_var.get().strip()
        definition = self.def_var.get().strip()
        if ref:
            self.callback(ref, definition)
        self.destroy()


class DefinitionListDialog(ModalDialog):
    """Dialog to create a definition list (term + up to 2 definitions)."""

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("Definition List")

        DLabel(self, text="Term:").grid(row=0, column=0, sticky="ne", padx=8, pady=6)
        self.term_var = tk.StringVar()
        DEntry(self, textvariable=self.term_var, width=240).grid(
            row=0, column=1, padx=4, pady=6
        )

        DLabel(self, text="Definition 1:").grid(
            row=1, column=0, sticky="e", padx=8, pady=6
        )
        self.def1_var = tk.StringVar()
        DEntry(self, textvariable=self.def1_var, width=240).grid(
            row=1, column=1, padx=4, pady=6
        )

        DLabel(self, text="Definition 2:").grid(
            row=2, column=0, sticky="e", padx=8, pady=6
        )
        self.def2_var = tk.StringVar()
        DEntry(self, textvariable=self.def2_var, width=240).grid(
            row=2, column=1, padx=4, pady=6
        )

        btn = ctk.CTkFrame(self, fg_color="transparent")
        btn.grid(row=3, column=0, columnspan=2, pady=8)
        DButton(btn, text="Insert", command=self._insert).pack(side=tk.LEFT, padx=4)
        DButton(btn, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=4)

        self.bind("<Return>", lambda e: self._insert())

    def _insert(self) -> None:
        term = self.term_var.get().strip()
        defs = [
            d for d in (self.def1_var.get().strip(), self.def2_var.get().strip()) if d
        ]
        if term and defs:
            lines = ["", term]
            lines.extend(f": {d}" for d in defs)
            self.callback("\n".join(lines))
        self.destroy()


class YAMLFrontMatterDialog(ModalDialog):
    """Dialog to add a YAML Front Matter block at the start of the document."""

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("YAML Front Matter")

        fields = ["lang", "title", "author", "description", "keywords"]
        self.vars: dict[str, tk.StringVar] = {}
        for i, field in enumerate(fields):
            DLabel(self, text=f"{field}:").grid(
                row=i, column=0, sticky="e", padx=8, pady=4
            )
            self.vars[field] = tk.StringVar()
            DEntry(self, textvariable=self.vars[field], width=280).grid(
                row=i, column=1, padx=4, pady=4
            )

        btn = ctk.CTkFrame(self, fg_color="transparent")
        btn.grid(row=len(fields), column=0, columnspan=2, pady=8)
        DButton(btn, text="Insert", command=self._insert).pack(side=tk.LEFT, padx=4)
        DButton(btn, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=4)

        self.bind("<Return>", lambda e: self._insert())

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


class DateTimeDialog(ModalDialog):
    """Dialog to insert the system date and/or time."""

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("Insert Date and Time")
        self.choice = tk.StringVar(value="date_time")

        DRadioButton(
            self, text="Date and time", variable=self.choice, value="date_time"
        ).grid(row=0, column=0, sticky="w", padx=12, pady=4)
        DRadioButton(self, text="Date only", variable=self.choice, value="date").grid(
            row=1, column=0, sticky="w", padx=12, pady=4
        )
        DRadioButton(self, text="Time only", variable=self.choice, value="time").grid(
            row=2, column=0, sticky="w", padx=12, pady=4
        )

        btn = ctk.CTkFrame(self, fg_color="transparent")
        btn.grid(row=3, column=0, pady=8)
        DButton(btn, text="Insert", command=self._insert).pack(side=tk.LEFT, padx=4)
        DButton(btn, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=4)

        self.bind("<Return>", lambda e: self._insert())

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


class AboutDialog(ModalDialog):
    """Dialog showing information about the application."""

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("About")
        icon = resource_path(os.path.join("images", "mark_editor.png"))
        if os.path.exists(icon):
            try:
                photo = tk.PhotoImage(file=icon)
                self.iconphoto(True, photo)
                self._photo_ref = photo
            except Exception:
                pass
        DLabel(
            self,
            text=f"{APP_NAME}, version {VERSION} ({RELEASE})",
        ).pack(padx=32, pady=(24, 12))
        DButton(self, text="Close", width=100, command=self.destroy).pack(pady=(0, 18))


# ═══════════════════════════════════════════════════════════════════════
# Main application
# ═══════════════════════════════════════════════════════════════════════


class MarkEditor(ctk.CTk):
    """The main Mark Editor application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        # Keep the window hidden until fully built to avoid a small
        # default-sized window flashing during theme-switch restarts.
        self.withdraw()
        self._restart_requested = False
        self._theme_mode = tk.StringVar(value=load_theme())

        self.converter = MarkdownToHTML()
        self.current_file: Path | None = None
        self.is_modified = False
        self.editor_font_size = EDITOR_FONT_SIZE
        self.interface_font_size = INTERFACE_FONT_SIZE

        # Resolve fonts.
        self.interface_font = (
            FONT_FAMILIES["sans"],
            self.interface_font_size,
            "normal",
        )
        self.editor_font = (FONT_FAMILIES["mono"], self.editor_font_size, "normal")
        self.editor_mono = (FONT_FAMILIES["mono"], self.editor_font_size - 1, "normal")

        self._build_menu()
        self._build_statusbar()
        self._build_panels()
        self._update_editor_colors()
        self._bind_shortcuts()
        self._restore_pending_text()
        self._update_title()
        self._update_status()
        self.geometry("1100x700")
        self.after(20, self.deiconify)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        colors = menu_colors()
        menu_font = (FONT_FAMILIES["sans"], MENU_FONT_SIZE, "normal")

        def new_menu(master) -> tk.Menu:
            return tk.Menu(
                master, tearoff=False, font=menu_font, borderwidth=0, **colors
            )

        menubar = new_menu(self)

        # ── File ──
        file_menu = new_menu(menubar)
        file_menu.add_command(
            label="New File", accelerator="Ctrl+N", command=self._on_new
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Open...", accelerator="Ctrl+O", command=self._on_open
        )
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
        edit_menu = new_menu(menubar)
        edit_menu.add_command(label="Undo", accelerator="Ctrl+Z", command=self._on_undo)
        edit_menu.add_command(
            label="Redo", accelerator="Ctrl+Shift+Z", command=self._on_redo
        )
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", accelerator="Ctrl+X", command=self._on_cut)
        edit_menu.add_command(label="Copy", accelerator="Ctrl+C", command=self._on_copy)
        edit_menu.add_command(
            label="Paste", accelerator="Ctrl+V", command=self._on_paste
        )
        edit_menu.add_separator()
        edit_menu.add_command(
            label="Find...", accelerator="Ctrl+F", command=self._on_find
        )
        edit_menu.add_command(
            label="Replace...", accelerator="Ctrl+R", command=self._on_replace
        )
        edit_menu.add_command(
            label="Replace All...",
            accelerator="Ctrl+Shift+R",
            command=self._on_replace_all,
        )
        edit_menu.add_separator()
        edit_menu.add_command(
            label="Select All", accelerator="Ctrl+A", command=self._on_select_all
        )
        edit_menu.add_command(
            label="Remove Selection",
            accelerator="Ctrl+Shift+A",
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
        format_menu = new_menu(menubar)
        format_menu.add_command(
            label="Bold",
            accelerator="Ctrl+B",
            command=lambda: self._wrap_selection("**"),
        )
        format_menu.add_command(
            label="Italic",
            accelerator="Ctrl+I",
            command=lambda: self._wrap_selection("*"),
        )
        format_menu.add_command(
            label="Underline",
            accelerator="Ctrl+U",
            command=lambda: self._wrap_selection("^^"),
        )
        format_menu.add_command(
            label="Strikethrough",
            accelerator="Ctrl+D",
            command=lambda: self._wrap_selection("~~"),
        )
        format_menu.add_separator()
        format_menu.add_command(
            label="Superscript",
            accelerator="Ctrl+Shift+P",
            command=lambda: self._wrap_selection("^"),
        )
        format_menu.add_command(
            label="Subscript",
            accelerator="Ctrl+Shift+B",
            command=lambda: self._wrap_selection("~"),
        )
        format_menu.add_command(
            label="Inline Code",
            accelerator="Ctrl+K",
            command=lambda: self._wrap_selection("`"),
        )
        format_menu.add_command(
            label="Mark",
            accelerator="Ctrl+Shift+M",
            command=lambda: self._wrap_selection("=="),
        )
        format_menu.add_separator()
        format_menu.add_command(
            label="Header ID...", accelerator="Ctrl+H", command=self._on_header_id
        )
        format_menu.add_command(
            label="Header Link...",
            accelerator="Ctrl+Shift+H",
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
            label="Language Marker...",
            accelerator="Ctrl+W",
            command=self._on_language_marker,
        )
        format_menu.add_command(
            label="Language Wrapping...",
            accelerator="Ctrl+Shift+W",
            command=self._on_language_wrapping,
        )
        format_menu.add_command(
            label="Furigana...", accelerator="Ctrl+Shift+J", command=self._on_furigana
        )
        format_menu.add_command(
            label="Date and Time...",
            accelerator="Ctrl+Shift+D",
            command=self._on_date_time,
        )
        format_menu.add_command(
            label="Special Mark",
            accelerator="Ctrl+Shift+L",
            command=self._on_special_mark,
        )
        format_menu.add_separator()
        cjk_menu = new_menu(menubar)
        for code in CJK_FONT_TAGS:
            cjk_menu.add_command(
                label=code,
                command=lambda c=code: self._insert_text(f"{{:{c}}}"),
            )
        format_menu.add_cascade(label="CJK Codes", menu=cjk_menu)
        emoji_menu = new_menu(menubar)
        for code in EMOJIS:
            emoji_menu.add_command(
                label=f":{code}:",
                command=lambda c=code: self._insert_text(f":{c}:"),
            )
        format_menu.add_cascade(label="Emoji Shortcodes", menu=emoji_menu)
        special_menu = new_menu(menubar)
        for name, code in SPECIAL_SIGNS:
            special_menu.add_command(
                label=f"{code} {name}",
                command=lambda c=code: self._insert_text(c),
            )
        format_menu.add_cascade(label="Special Signs", menu=special_menu)
        format_menu.add_separator()
        format_menu.add_command(
            label="Clear Formatting",
            accelerator="Ctrl+Shift+F",
            command=self._on_clear_formatting,
        )
        menubar.add_cascade(label="Format", menu=format_menu)

        # ── Paragraph ──
        para_menu = new_menu(menubar)
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
            label="Unordered List",
            accelerator="Ctrl+Shift+G",
            command=self._on_unordered_list,
        )
        para_menu.add_command(
            label="Definition List...",
            accelerator="Ctrl+Shift+X",
            command=self._on_definition_list,
        )
        para_menu.add_separator()
        para_menu.add_command(
            label="Code Block...",
            accelerator="Ctrl+Shift+K",
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
            label="Horizontal Rule",
            accelerator="Ctrl+_",
            command=self._on_horizontal_rule,
        )
        para_menu.add_separator()
        para_menu.add_command(
            label="Add Indent", accelerator="Tab", command=self._on_add_indent
        )
        para_menu.add_command(
            label="Remove Indent",
            accelerator="Shift+Tab",
            command=self._on_remove_indent,
        )
        para_menu.add_separator()
        para_menu.add_command(
            label="Comment...", accelerator="Ctrl+M", command=self._on_comment
        )
        para_menu.add_command(
            label="YAML Front Matter...",
            accelerator="Ctrl+Shift+Y",
            command=self._on_yaml_front_matter,
        )
        menubar.add_cascade(label="Paragraph", menu=para_menu)

        # ── View ──
        view_menu = new_menu(menubar)
        view_menu.add_command(
            label="Toggle Theme",
            accelerator="Ctrl+Shift+T",
            command=self._on_toggle_theme,
        )
        view_menu.add_radiobutton(
            label="Light Theme",
            variable=self._theme_mode,
            value="light",
            command=lambda: self._apply_theme("light"),
        )
        view_menu.add_radiobutton(
            label="Dark Theme",
            variable=self._theme_mode,
            value="dark",
            command=lambda: self._apply_theme("dark"),
        )
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
        help_menu = new_menu(menubar)
        help_menu.add_command(
            label="Markdown Guide", command=self._on_help_markdown_guide
        )
        help_menu.add_command(label="About Editor", command=self._on_help_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def _build_panels(self) -> None:
        # ── single, full-width editing panel ──
        editor_frame = ctk.CTkFrame(self, fg_color="transparent")
        editor_row = ctk.CTkFrame(editor_frame, fg_color="transparent")

        colors = editor_colors()
        self._line_numbers = tk.Text(
            editor_row,
            width=4,
            bg=colors["gutter_bg"],
            fg=colors["gutter_fg"],
            insertbackground=colors["insert"],
            font=(self.editor_mono[0], self.editor_font_size - 2, "normal"),
            padx=4,
            pady=8,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            takefocus=0,
            cursor="arrow",
            state=tk.DISABLED,
        )
        self._line_numbers.pack(side=tk.LEFT, fill=tk.Y)

        self._editor_vbar = ctk.CTkScrollbar(editor_row, orientation="vertical")
        self._editor = tk.Text(
            editor_row,
            bg=colors["bg"],
            fg=colors["fg"],
            insertbackground=colors["insert"],
            font=self.editor_font,
            wrap=tk.WORD,
            undo=True,
            padx=8,
            pady=8,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=colors["border"],
            yscrollcommand=self._on_editor_scroll,
        )
        self._editor_vbar.configure(command=self._editor.yview)
        self._editor_vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._editor.pack(fill=tk.BOTH, expand=True)
        self._editor.configure(
            font=(self.editor_font[0], self.editor_font_size, "normal")
        )
        self._editor.tag_configure(
            "code", font=(self.editor_mono[0], self.editor_font_size - 1, "normal")
        )
        for key in CJK_TAG_KEYS:
            self._editor.tag_configure(
                key, font=(FONT_FAMILIES[key], self.editor_font_size)
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
        self._status_var = tk.StringVar(value="Ln 1, Col 1")
        # Paint the bar with the active colour theme's primary accent so
        # the blue / dark-blue theme is visible in the main window.
        accent = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        bar = ctk.CTkFrame(self, corner_radius=0, fg_color=accent, height=34)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        status = ctk.CTkLabel(
            bar,
            textvariable=self._status_var,
            anchor="e",
            fg_color="transparent",
            text_color=("#FFFFFF", "#F2F6FF"),
            font=(self.editor_font[0], STATUS_FONT_SIZE, "normal"),
        )
        status.pack(fill=tk.X, padx=18, pady=6)

    def _update_editor_colors(self) -> None:
        """Apply the colours matching the active appearance mode."""
        if not hasattr(self, "_editor") or not hasattr(self, "_line_numbers"):
            return
        colors = editor_colors()
        self._editor.configure(
            bg=colors["bg"],
            fg=colors["fg"],
            insertbackground=colors["insert"],
            highlightbackground=colors["border"],
            highlightcolor=colors["border"],
        )
        self._line_numbers.configure(
            bg=colors["gutter_bg"],
            fg=colors["gutter_fg"],
            insertbackground=colors["insert"],
        )

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
            "Text",
            "<Control-x>",
            lambda e: self._on_cut() if e.widget == self._editor else None,
        )
        self.bind_class(
            "Text",
            "<Control-c>",
            lambda e: self._on_copy() if e.widget == self._editor else None,
        )
        self.bind_class(
            "Text",
            "<Control-v>",
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
        self.bind_all("<Control-Shift-T>", lambda e: self._on_toggle_theme())
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
        self._apply_language_fonts()

    def _apply_language_fonts(self) -> None:
        """Tag blocks after {:lang} markers with the matching CJK font.

        A marker like {:ja} switches the font starting at the beginning of
        the next line (header / paragraph / code block). The switch ends
        at the closing {:} marker, or at the end of that line when no
        closing marker follows.
        """
        content = self._editor.get("1.0", "end-1c")
        for key in CJK_TAG_KEYS:
            self._editor.tag_remove(key, "1.0", tk.END)
        tag_map = {k.lower(): v for k, v in CJK_FONT_TAGS.items()}
        marker_re = re.compile(r"\{:([A-Za-z][A-Za-z0-9-]*)\}")
        pos = 0
        while True:
            match = marker_re.search(content, pos)
            if not match:
                break
            key = tag_map.get(match.group(1).lower())
            newline = content.find("\n", match.end())
            start = len(content) if newline == -1 else newline + 1
            close = content.find("{:}", start)
            if key and start < len(content):
                if close != -1:
                    end_pos = close
                    pos = close + 3
                else:
                    line_end = content.find("\n", start)
                    end_pos = len(content) if line_end == -1 else line_end
                    pos = match.end()
                if end_pos > start:
                    self._editor.tag_add(key, f"1.0+{start}c", f"1.0+{end_pos}c")
            else:
                pos = match.end()

    def _msg(self, title: str, message: str, icon: str = "info") -> None:
        """Show a themed message box."""
        CTkMessagebox(
            self,
            title=title,
            message=message,
            icon=icon,
            font=dialog_font(),
        )

    # ── File operations ───────────────────────────────────────────────

    def _check_save(self) -> bool:
        """Ask the user about saving before closing. Returns True to proceed."""
        if not self.is_modified:
            return True
        box = CTkMessagebox(
            self,
            title="Save changes",
            message="Save the opened file?",
            icon="question",
            options=["Yes", "No"],
            font=dialog_font(),
        )
        if box.get() == "Yes":
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
        path = ask_open_path(
            "Open file",
            [("Markdown files", "*.md *.markdown"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8")
        except Exception as exc:
            self._msg("Open file", str(exc), "cancel")
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
            self._msg("Reopen file", str(exc), "cancel")
            return
        self._editor.delete("1.0", tk.END)
        self._editor.insert("1.0", text)
        self.is_modified = False
        self._editor.edit_modified(False)
        self._update_title()
        self._update_line_numbers()
        self._msg("Reopen file", "File reopened!", "check")

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
            self._msg("Save file", str(exc), "cancel")
            return
        self._msg("Save file", "File saved!", "check")

    def _on_save_as(self) -> bool:
        path = ask_save_path(
            "Save As",
            defaultextension=".md",
            initialfile=(
                self.current_file.name if self.current_file else "untitled.md"
            ),
            filetypes=[("Markdown files", "*.md *.markdown"), ("All files", "*.*")],
        )
        if not path:
            return False
        self._save_to(Path(path))
        return True

    def _on_convert(self) -> None:
        formats = [
            "HTML5 file (.html)",
            "HTML5 file with CSS3 (.html)",
            "Plain text file (.txt)",
            "PDF file (.pdf)",
        ]
        dlg = ChoiceDialog(
            self,
            prompt="Choose the target format:",
            items=formats,
            initial=formats[0],
        )
        dlg.grab_set()
        self.wait_window(dlg)
        choice = dlg.result
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
        if base.endswith((".md", ".markdown")):
            base = base.rsplit(".", 1)[0]
        path = ask_save_path(
            "Convert",
            defaultextension=ext,
            initialfile=base + ext,
            filetypes=ftype,
        )
        if not path:
            return
        try:
            self._perform_convert(Path(path), ext, include_css=include_css)
        except Exception as exc:
            self._msg("Convert", str(exc), "cancel")
            return
        self._msg("Convert", "Conversion complete!", "check")

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
        text = re.sub(r"^```[^\n]*\n?", "", text, flags=re.MULTILINE)
        text = re.sub(r"^#+\s?", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*([-*+>])\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*(\|\s*)+$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^---\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^:::+\s*$", "", text, flags=re.MULTILINE)
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
        dlg.grab_set()

    def _on_replace(self) -> None:
        dlg = ReplaceDialog(self, self._editor)
        dlg.grab_set()

    def _on_replace_all(self) -> None:
        dlg = ReplaceDialog(self, self._editor)
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
            self._editor.tag_add(
                tk.SEL, sel_start, f"{sel_start}+{len(wrapper + text + wrapper)}c"
            )
            self._editor.mark_set(tk.INSERT, f"{sel_start}+{len(wrapper)}c")
        else:
            self._editor.insert(tk.INSERT, f"{wrapper}{wrapper}")
            self._editor.mark_set(tk.INSERT, f"insert-{len(wrapper)}c")
        self._editor.focus_set()

    def _on_header_id(self) -> None:
        line = self._get_current_line_text()
        hid = ask_string("Enter the header ID (without #):", "Header ID")
        if not hid:
            return
        hid = hid.strip().lstrip("#")
        if line.strip():
            self._replace_current_line(f"{line.rstrip()} {{#{hid}}}")
        else:
            # Empty line: create a new heading carrying only the ID.
            self._replace_current_line(f"# {{#{hid}}}")

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
        url = ask_string("Enter the URL:", "Hyperlink")
        if not url:
            return
        text = selected or ask_string("Enter the link text:", "Hyperlink") or url
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
        lang = ask_string("Enter a BCP 47 language tag (e.g. de):", "Language Marker")
        if not lang:
            return
        lang = lang.strip()
        line = self._get_current_line_text()
        self._replace_current_line(f"{{:{lang}}} {line}")
        self._editor.focus_set()

    def _on_language_wrapping(self) -> None:
        lang = ask_string("Enter a BCP 47 language tag (e.g. fr):", "Language Wrapping")
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
            self._editor.insert(tk.INSERT, f"{{:{lang}}}{{:}}")
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
        lang = (
            ask_string("Enter the programming language (optional):", "Code Block") or ""
        )
        lang = lang.strip()
        text = self._get_current_line_text()
        self._add_blank_line_before_if_needed()
        self._replace_current_line(f"```{lang}\n{text}\n```")

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
        path = ask_open_path(
            "Choose an image",
            [("Images", "*.png *.jpg *.jpeg *.gif *.svg *.webp"), ("All files", "*.*")],
        )
        if not path:
            return
        alt = ask_string("Enter the Alt text:", "Image") or ""
        title = ask_string("Enter an Optional title (or leave empty):", "Image") or ""
        alt = alt.strip()
        title = title.strip()
        if title:
            markdown = f'![{alt}]({path} "{title}")'
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
        comment = ask_string("Enter the comment text:", "Comment")
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
            self._msg(
                "YAML Front Matter",
                "The document already has a YAML Front Matter block.",
                "warning",
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
        new = "dark" if current_mode() == "Light" else "light"
        self._apply_theme(new)

    def _apply_theme(self, name: str) -> None:
        """Save the requested appearance mode and restart to apply it.

        CustomTkinter applies set_default_color_theme() only to widgets
        created afterwards, so the whole window is rebuilt by relaunching
        the application with the new colour theme set before CTk() is
        created. Unsaved text is preserved through the cache directory.
        """
        name = name.lower()
        if name not in THEMES or self._restart_requested:
            return
        save_theme(name)
        try:
            text = self._editor.get("1.0", "end-1c")
            if text:
                ensure_cache_dir().joinpath(TEMP_MD).write_text(text, encoding="utf-8")
        except Exception:
            pass
        self._restart_requested = True
        self.destroy()

    def _restore_pending_text(self) -> None:
        """Restore unsaved text preserved across a theme-switch restart."""
        pending = ensure_cache_dir() / TEMP_MD
        try:
            if pending.exists():
                text = pending.read_text(encoding="utf-8")
                if text.strip():
                    self._editor.insert("1.0", text)
                    self.is_modified = True
                    self._update_line_numbers()
                    self._update_title()
                pending.unlink()
        except Exception:
            pass

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
        for key in CJK_TAG_KEYS:
            self._editor.tag_configure(key, font=(FONT_FAMILIES[key], new_size))
        self._line_numbers.configure(font=(self.editor_mono[0], new_size - 2, "normal"))
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
            self._msg("Quick View", str(exc), "cancel")
            return
        webbrowser.open(html_path.as_uri())

    # ── Help operations ───────────────────────────────────────────────

    def _on_help_markdown_guide(self) -> None:
        webbrowser.open("https://www.markdownguide.org/")

    def _on_help_about(self) -> None:
        about = AboutDialog(self)
        about.grab_set()


# ═══════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════


def main() -> None:
    restart = True
    while restart:
        # set_default_color_theme() must run strictly before the main
        # window (ctk.CTk) is created, hence this construction loop.
        # STEP 1 (before ctk.CTk() is created inside MarkEditor):
        # configure appearance and colour theme.
        mode = load_theme()
        ctk.set_appearance_mode(mode.capitalize())
        ctk.set_widget_scaling(1.0)
        apply_color_theme(mode)
        # STEP 2: initialize the main window — widgets now use the theme.
        app = MarkEditor()
        app.mainloop()
        restart = getattr(app, "_restart_requested", False)


if __name__ == "__main__":
    main()
