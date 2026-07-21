#!/usr/bin/env python3
"""Mark Editor — a simple Markdown editor with live preview.

Built with Python 3.13+, Tkinter, Python-Markdown, and PyMdown Extensions.
"""

from __future__ import annotations

import html.parser
import os
import re
import subprocess
import sys
import webbrowser
import tkinter as tk
from tkinter.font import Font

import ttkbootstrap as tb
from ttkbootstrap.dialogs import Messagebox, Querybox
from datetime import datetime
from typing import Optional

import markdown
from markdown.extensions.tables import TableExtension

try:
    import pypandoc

    HAS_PYPANDOC = True
except ImportError:
    HAS_PYPANDOC = False

try:
    from PIL import Image, ImageTk

    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

__version__ = "0.3"
__app_name__ = "Mark Editor"


def resource_path(relative: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base, relative)


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------


def font_installed(family: str) -> bool:
    try:
        f = Font(family=family, size=10)
        return f.actual("family") == family
    except Exception:
        return False


def resolve_font(
    category: str,
    user: str,
    fallback1: str,
    fallback2: str,
    size: int = 14,
    weight: str = "normal",
    slant: str = "roman",
) -> Font:
    family = (
        user
        if font_installed(user)
        else fallback1 if font_installed(fallback1) else fallback2
    )
    return Font(family=family, size=size, weight=weight, slant=slant)


# ---------------------------------------------------------------------------
# HTML → Tkinter Text renderer
# ---------------------------------------------------------------------------


class TkHTMLRenderer(html.parser.HTMLParser):
    """Parse HTML (produced by markdown) and render into a tk.Text widget."""

    def __init__(
        self,
        text_widget: tk.Text,
        body_font: Font,
        heading_base: tuple[str, str],
        code_font: Font,
        base_dir: str = "",
    ) -> None:
        super().__init__()
        self.text_widget = text_widget
        self.body_font = body_font
        self.heading_base = heading_base
        self.code_font = code_font
        self._tag_stack: list[str] = []
        self._text_buffer: list[str] = []
        self._image_refs: list[ImageTk.PhotoImage] = []
        self._table_refs: list[tk.Widget] = []
        self._base_dir = base_dir
        self._preformatted = False
        self._in_li = False
        self._first_li = False
        self._list_stack: list[tuple[str, int]] = []

        self._table_rows: list[list[str]] = []
        self._table_headers: list[str] = []
        self._current_row: list[str] = []
        self._current_cell: list[str] = []
        self._in_table = False
        self._in_header = False

        self._in_ruby = False
        self._in_rt = False
        self._ruby_base = ""
        self._ruby_rt = ""

    def _inside_list(self) -> bool:
        for tag in reversed(self._tag_stack):
            if tag in ("ul", "ol"):
                return True
            if tag in ("blockquote", "pre"):
                return False
        return False

    def _flush(self) -> None:
        if not self._text_buffer:
            return
        txt = "".join(self._text_buffer)
        if self._preformatted:
            self.text_widget.insert(tk.END, txt, ("code", *self._tag_stack))
        else:
            self.text_widget.insert(tk.END, txt, tuple(self._tag_stack))
        self._text_buffer = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower == "p" and self._in_li:
            self._tag_stack.append("p")
            return
        self._flush()
        attr_dict = dict(attrs)

        if tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._tag_stack.append(f"h{tag_lower[1]}")
        elif tag_lower == "p":
            self._tag_stack.append("p")
        elif tag_lower in ("strong", "b"):
            self._tag_stack.append(self._resolve_font_tag("bold"))
        elif tag_lower in ("em", "i"):
            self._tag_stack.append(self._resolve_font_tag("italic"))
        elif tag_lower in ("u", "ins"):
            self._tag_stack.append("u")
        elif tag_lower in ("s", "del"):
            self._tag_stack.append("del")
        elif tag_lower == "mark":
            self._tag_stack.append("mark")
        elif tag_lower == "sub":
            self._tag_stack.append("sub")
        elif tag_lower == "sup":
            self._tag_stack.append("sup")
        elif tag_lower == "code":
            cls = attr_dict.get("class", "")
            if cls and cls.startswith("language-"):
                lang = cls[len("language-") :]
                self.text_widget.insert(tk.END, f"\n  {lang}\n", ("code_header",))
            self._tag_stack.append("code")
        elif tag_lower == "pre":
            self._preformatted = True
            self._tag_stack.append("pre")
        elif tag_lower == "blockquote":
            self._tag_stack.append("blockquote")
        elif tag_lower == "a":
            self._tag_stack.append("link")
        elif tag_lower == "div":
            pass
        elif tag_lower in ("ul", "ol"):
            self._tag_stack.append(tag_lower)
            self._list_stack.append((tag_lower, 0))
            self._first_li = True
        elif tag_lower == "li":
            if self._list_stack:
                ltype, counter = self._list_stack[-1]
                if ltype == "ol":
                    counter += 1
                    self._list_stack[-1] = (ltype, counter)
                    prefix = f"  {counter}. "
                else:
                    prefix = "  • "
            else:
                prefix = "  - "
            if self._first_li:
                self._first_li = False
            else:
                prefix = "\n" + prefix
            self._text_buffer.append(prefix)
            self._tag_stack.append("li")
            self._in_li = True
        elif tag_lower == "table":
            self._in_table = True
            self._tag_stack.append("table")
            self._table_rows = []
            self._table_headers = []
            self._current_row = []
        elif tag_lower in ("thead", "tbody"):
            self._in_header = tag_lower == "thead"
        elif tag_lower == "tr":
            self._current_row = []
        elif tag_lower in ("th", "td"):
            self._current_cell = []
            self._tag_stack.append(tag_lower)
        elif tag_lower == "br":
            self._text_buffer.append("\n")
        elif tag_lower == "hr":
            self._flush()
            self.text_widget.insert(tk.END, "─" * 40 + "\n", ("hr",))
        elif tag_lower == "img":
            src = attr_dict.get("src", "")
            alt = attr_dict.get("alt", "")
            self._flush()
            if HAS_PILLOW and src:
                full = (
                    os.path.join(self._base_dir, src) if not os.path.isabs(src) else src
                )
                if os.path.exists(full):
                    try:
                        img = Image.open(full)
                        max_w = 400
                        if img.width > max_w:
                            ratio = max_w / img.width
                            img = img.resize(
                                (max_w, int(img.height * ratio)), Image.LANCZOS
                            )
                        photo = ImageTk.PhotoImage(img)
                        self._image_refs.append(photo)
                        self.text_widget.insert(tk.END, "\n  ")
                        self.text_widget.image_create(tk.END, image=photo)
                        self.text_widget.insert(tk.END, "  \n")
                        return
                    except Exception:
                        pass
            label = f"{alt} ({src})" if alt and src else (alt or src)
            self.text_widget.insert(tk.END, f"  [{label}]  \n", ("img",))
        elif tag_lower == "ruby":
            self._in_ruby = True
            self._in_rt = False
            self._ruby_base = ""
            self._ruby_rt = ""
        elif tag_lower == "rt":
            self._in_rt = True
        elif tag_lower == "dl":
            self._tag_stack.append("p")
        elif tag_lower == "dt":
            pass
        elif tag_lower == "dd":
            self._text_buffer.append("\n  ")
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        self._flush()
        tag_lower = tag.lower()

        if tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._remove_tag(f"h{tag_lower[1]}")
            self._text_buffer.append("\n")
        elif tag_lower == "p":
            self._remove_tag("p")
            if not self._in_li:
                self._text_buffer.append("\n")
        elif tag_lower in ("strong", "b"):
            self._tag_stack = [t for t in self._tag_stack if not t.startswith("bold")]
        elif tag_lower in ("em", "i"):
            self._tag_stack = [
                t
                for t in self._tag_stack
                if not (t.startswith("italic") or t.startswith("bold_italic"))
            ]
        elif tag_lower in ("u", "ins"):
            self._remove_tag("u")
        elif tag_lower in ("s", "del"):
            self._remove_tag("del")
        elif tag_lower == "mark":
            self._remove_tag("mark")
        elif tag_lower == "sub":
            self._remove_tag("sub")
        elif tag_lower == "sup":
            self._remove_tag("sup")
        elif tag_lower == "code":
            self._remove_tag("code")
        elif tag_lower == "pre":
            self._preformatted = False
            self._remove_tag("pre")
            self._text_buffer.append("\n")
        elif tag_lower == "blockquote":
            self._remove_tag("blockquote")
            self._text_buffer.append("\n")
        elif tag_lower == "a":
            self._remove_tag("link")
        elif tag_lower == "div":
            pass
        elif tag_lower in ("ul", "ol"):
            self._remove_tag(tag_lower)
            if self._list_stack:
                self._list_stack.pop()
            self._text_buffer.append("\n")
        elif tag_lower == "li":
            self._remove_tag("li")
            self._in_li = False
        elif tag_lower == "table":
            self._render_table()
            self._remove_tag("table")
            self._in_table = False
            self._text_buffer.append("\n")
        elif tag_lower in ("thead", "tbody"):
            self._in_header = False
        elif tag_lower == "tr":
            row_cells = list(self._current_row)
            if self._in_header:
                self._table_headers.append(row_cells)
            else:
                self._table_rows.append(row_cells)
            self._current_row = []
        elif tag_lower in ("th", "td"):
            self._current_row.append("".join(self._current_cell))
            self._current_cell = []
            self._remove_tag(tag_lower)
        elif tag_lower == "ruby":
            if self._ruby_base and self._ruby_rt:
                self._text_buffer.append(self._ruby_base)
                self._text_buffer.append(f"\u3010{self._ruby_rt}\u3011")
            elif self._ruby_base:
                self._text_buffer.append(self._ruby_base)
            self._in_ruby = False
            self._in_rt = False
        elif tag_lower == "rt":
            self._in_rt = False
        elif tag_lower == "dl":
            self._remove_tag("p")
        elif tag_lower == "dt":
            self._text_buffer.append("\n")
        elif tag_lower == "dd":
            self._text_buffer.append("\n")

    def _render_table(self) -> None:
        col_count = 0
        if self._table_headers:
            col_count = max(col_count, max(len(r) for r in self._table_headers))
        if self._table_rows:
            col_count = max(col_count, max(len(r) for r in self._table_rows))
        if col_count == 0:
            return

        all_rows: list[list[str]] = []
        if self._table_headers:
            all_rows.extend(self._table_headers)
        all_rows.extend(self._table_rows)

        col_widths = [0] * col_count
        for row in all_rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(cell))

        mono_name = self.code_font.cget("family")
        mono_size = self.code_font.cget("size")

        table_frame = tk.Frame(
            self.text_widget,
            highlightbackground="#dee2e6",
            highlightthickness=1,
        )
        table_frame._tb_no_autostyle = True

        for row_idx, row in enumerate(all_rows):
            is_header = self._table_headers and row_idx < len(self._table_headers)
            bg = "#e9ecef" if is_header else "#ffffff"
            fg = "black"
            font_spec = (
                (mono_name, mono_size, "bold") if is_header else (mono_name, mono_size)
            )

            for col_idx in range(col_count):
                text = row[col_idx] if col_idx < len(row) else ""
                cell_width = max(col_widths[col_idx] + 2, 6)

                cell = tk.Label(
                    table_frame,
                    text=text,
                    font=font_spec,
                    fg=fg,
                    bg=bg,
                    relief="solid",
                    borderwidth=0,
                    highlightbackground="#dee2e6",
                    highlightthickness=1,
                    padx=6,
                    pady=2,
                    width=cell_width,
                    height=1,
                    anchor="w",
                )
                cell._tb_no_autostyle = True
                cell.grid(row=row_idx, column=col_idx, sticky="nsew")

        for i in range(col_count):
            table_frame.columnconfigure(i, weight=0)

        table_frame.pack(fill="x", padx=10, pady=5)
        self.text_widget.window_create(tk.END, window=table_frame)
        self._table_refs.append(table_frame)
        self.text_widget.insert(tk.END, "\n")

    def _resolve_font_tag(self, tag_type: str) -> str:
        tag_stack = self._tag_stack
        suffix = ""
        if any(t in ("code", "pre") for t in tag_stack):
            suffix = "_mono"
        elif any(t.startswith("h") for t in tag_stack):
            suffix = "_sans"
        if any(t.startswith("italic") for t in tag_stack):
            return f"bold_italic{suffix}"
        return f"{tag_type}{suffix}"

    def _remove_tag(self, tag: str) -> None:
        while tag in self._tag_stack:
            self._tag_stack.remove(tag)

    def _in_table_cell(self) -> bool:
        return "th" in self._tag_stack or "td" in self._tag_stack

    def _is_ws_only(self, data: str) -> bool:
        return data.strip() == ""

    def handle_data(self, data: str) -> None:
        if self._in_ruby:
            if self._in_rt:
                self._ruby_rt += data
            else:
                self._ruby_base += data
            return
        if self._in_table_cell():
            self._current_cell.append(data)
            return
        if self._in_table and "table" in self._tag_stack:
            return
        if self._tag_stack and self._tag_stack[-1] in ("dt", "dd"):
            self._text_buffer.append(data)
            return
        if self._is_ws_only(data) and (self._in_li or self._in_table):
            return
        self._text_buffer.append(data)

    def handle_entityref(self, name: str) -> None:
        char = html.entities.name2codepoint.get(name)
        text = chr(char) if char else f"&{name};"
        if self._in_table_cell():
            self._current_cell.append(text)
        else:
            self._text_buffer.append(text)

    def handle_charref(self, name: str) -> None:
        try:
            if name.startswith("x"):
                text = chr(int(name[1:], 16))
            else:
                text = chr(int(name))
        except ValueError:
            text = f"&#{name};"
        if self._in_table_cell():
            self._current_cell.append(text)
        else:
            self._text_buffer.append(text)


# ---------------------------------------------------------------------------
# Custom dialogs
# ---------------------------------------------------------------------------


class FindDialog(tb.Toplevel):
    def __init__(self, parent: tk.Tk, text_widget: tk.Text) -> None:
        super().__init__(parent)
        self.title("Find")
        self.text_widget = text_widget
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.use_regex = tb.BooleanVar(value=False)

        tb.Label(self, text="Find:").grid(row=0, column=0, sticky="e", padx=8, pady=6)
        self.find_var = tb.StringVar()
        tb.Entry(self, textvariable=self.find_var, width=30).grid(
            row=0, column=1, columnspan=2, padx=8, pady=6
        )

        tb.Checkbutton(self, text="Use regex", variable=self.use_regex).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=8, pady=4
        )

        btn_frame = tb.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=10)
        tb.Button(
            btn_frame, text="Find Next", command=self.find_next, bootstyle="primary"
        ).pack(side=tk.LEFT, padx=3)
        tb.Button(
            btn_frame, text="Close", command=self.destroy, bootstyle="secondary"
        ).pack(side=tk.LEFT, padx=3)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.find_var.trace_add("write", lambda *_: self._clear_highlights())

    def _get_pattern(self) -> str:
        text = self.find_var.get()
        if not self.use_regex.get():
            text = re.escape(text)
        return text

    def _clear_highlights(self) -> None:
        self.text_widget.tag_remove("find_match", "1.0", tk.END)

    def find_next(self) -> bool:
        self._clear_highlights()
        pattern = self._get_pattern()
        if not pattern:
            return False
        try:
            cur = self.text_widget.index(tk.INSERT)
            start = self.text_widget.search(
                pattern, cur, tk.END, regexp=True, nocase=True
            )
            if not start:
                start = self.text_widget.search(
                    pattern, "1.0", cur, regexp=True, nocase=True
                )
            if start:
                end = f"{start}+{len(self.text_widget.get(start, f'{start}+1c'))}c"
                self.text_widget.tag_add("find_match", start, end)
                self.text_widget.tag_config("find_match", background="yellow")
                self.text_widget.mark_set(tk.INSERT, end)
                self.text_widget.see(start)
                return True
        except re.error:
            pass
        return False


class ReplaceDialog(tb.Toplevel):
    def __init__(self, parent: tk.Tk, text_widget: tk.Text) -> None:
        super().__init__(parent)
        self.title("Replace")
        self.text_widget = text_widget
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.use_regex = tb.BooleanVar(value=False)

        tb.Label(self, text="Find:").grid(row=0, column=0, sticky="e", padx=8, pady=6)
        self.find_var = tb.StringVar()
        tb.Entry(self, textvariable=self.find_var, width=30).grid(
            row=0, column=1, columnspan=2, padx=8, pady=6
        )

        tb.Label(self, text="Replace:").grid(
            row=1, column=0, sticky="e", padx=8, pady=6
        )
        self.replace_var = tb.StringVar()
        tb.Entry(self, textvariable=self.replace_var, width=30).grid(
            row=1, column=1, columnspan=2, padx=8, pady=6
        )

        tb.Checkbutton(self, text="Use regex", variable=self.use_regex).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=8, pady=4
        )

        btn_frame = tb.Frame(self)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=10)
        tb.Button(
            btn_frame,
            text="Find Next",
            command=self.find_next,
            bootstyle="primary-outline",
        ).pack(side=tk.LEFT, padx=3)
        tb.Button(
            btn_frame, text="Replace", command=self.replace_one, bootstyle="primary"
        ).pack(side=tk.LEFT, padx=3)
        tb.Button(
            btn_frame, text="Replace All", command=self.replace_all, bootstyle="success"
        ).pack(side=tk.LEFT, padx=3)
        tb.Button(
            btn_frame, text="Close", command=self.destroy, bootstyle="secondary"
        ).pack(side=tk.LEFT, padx=3)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.find_var.trace_add("write", lambda *_: self._clear_highlights())

    def _get_pattern(self) -> str:
        text = self.find_var.get()
        if not self.use_regex.get():
            text = re.escape(text)
        return text

    def _clear_highlights(self) -> None:
        self.text_widget.tag_remove("find_match", "1.0", tk.END)

    def find_next(self) -> bool:
        self._clear_highlights()
        pattern = self._get_pattern()
        if not pattern:
            return False
        try:
            cur = self.text_widget.index(tk.INSERT)
            start = self.text_widget.search(
                pattern, cur, tk.END, regexp=True, nocase=True
            )
            if not start:
                start = self.text_widget.search(
                    pattern, "1.0", cur, regexp=True, nocase=True
                )
            if start:
                end = f"{start}+{len(self.text_widget.get(start, f'{start}+1c'))}c"
                self.text_widget.tag_add("find_match", start, end)
                self.text_widget.tag_config("find_match", background="yellow")
                self.text_widget.mark_set(tk.INSERT, end)
                self.text_widget.see(start)
                return True
        except re.error:
            pass
        return False

    def replace_one(self) -> None:
        if not self.find_next():
            return
        sel = self.text_widget.tag_ranges("find_match")
        if sel:
            start, end = sel[0], sel[1]
            replace_text = self.replace_var.get()
            self.text_widget.delete(start, end)
            self.text_widget.insert(start, replace_text)
            self.text_widget.tag_remove("find_match", "1.0", tk.END)

    def replace_all(self) -> None:
        pattern = self._get_pattern()
        if not pattern:
            return
        replace_text = self.replace_var.get()
        try:
            content = self.text_widget.get("1.0", tk.END)
            new_content, count = re.subn(
                pattern, replace_text, content, flags=re.MULTILINE
            )
            if count:
                self.text_widget.delete("1.0", tk.END)
                self.text_widget.insert("1.0", new_content)
                Messagebox.show_info(
                    f"Replaced {count} occurrence(s).", "Replace All", parent=self
                )
        except re.error as e:
            Messagebox.show_error(str(e), "Regex Error", parent=self)


class TableDialog(tb.Toplevel):
    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("Insert Table")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result: Optional[str] = None

        tb.Label(self, text="Columns:").grid(
            row=0, column=0, sticky="e", padx=8, pady=6
        )
        self.cols_var = tb.IntVar(value=3)
        tb.Spinbox(self, from_=1, to=20, textvariable=self.cols_var, width=5).grid(
            row=0, column=1, padx=8, pady=6
        )

        tb.Label(self, text="Rows:").grid(row=1, column=0, sticky="e", padx=8, pady=6)
        self.rows_var = tb.IntVar(value=3)
        tb.Spinbox(self, from_=1, to=50, textvariable=self.rows_var, width=5).grid(
            row=1, column=1, padx=8, pady=6
        )

        btn_frame = tb.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        tb.Button(
            btn_frame, text="Insert", command=self._insert, bootstyle="primary"
        ).pack(side=tk.LEFT, padx=3)
        tb.Button(
            btn_frame, text="Cancel", command=self.destroy, bootstyle="secondary"
        ).pack(side=tk.LEFT, padx=3)

    def _insert(self) -> None:
        cols = self.cols_var.get()
        rows = self.rows_var.get()
        lines = []
        header = "| " + " | ".join(f"Header {i + 1}" for i in range(cols)) + " |"
        sep = "| " + " | ".join("---" for _ in range(cols)) + " |"
        lines.append(header)
        lines.append(sep)
        for r in range(rows):
            cells = " | ".join(f"Cell {r + 1}-{c + 1}" for c in range(cols))
            lines.append(f"| {cells} |")
        self.result = "\n".join(lines)
        self.destroy()


class FuriganaDialog(tb.Toplevel):
    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("Insert Furigana")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result: Optional[str] = None

        tb.Label(self, text="Kanji / Text:").grid(
            row=0, column=0, sticky="e", padx=8, pady=6
        )
        self.kanji_var = tb.StringVar()
        tb.Entry(self, textvariable=self.kanji_var, width=25).grid(
            row=0, column=1, padx=8, pady=6
        )

        tb.Label(self, text="Reading (ruby):").grid(
            row=1, column=0, sticky="e", padx=8, pady=6
        )
        self.reading_var = tb.StringVar()
        tb.Entry(self, textvariable=self.reading_var, width=25).grid(
            row=1, column=1, padx=8, pady=6
        )

        btn_frame = tb.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        tb.Button(
            btn_frame, text="Insert", command=self._insert, bootstyle="primary"
        ).pack(side=tk.LEFT, padx=3)
        tb.Button(
            btn_frame, text="Cancel", command=self.destroy, bootstyle="secondary"
        ).pack(side=tk.LEFT, padx=3)

    def _insert(self) -> None:
        kanji = self.kanji_var.get()
        reading = self.reading_var.get()
        if kanji:
            self.result = f"<ruby>{kanji}<rt>{reading}</rt></ruby>"
        self.destroy()


class HeaderLinkDialog(tb.Toplevel):
    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("Header Link")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result: Optional[str] = None

        tb.Label(self, text="Header ID:").grid(
            row=0, column=0, sticky="e", padx=8, pady=6
        )
        self.id_var = tb.StringVar()
        tb.Entry(self, textvariable=self.id_var, width=25).grid(
            row=0, column=1, padx=8, pady=6
        )

        tb.Label(self, text="Link text:").grid(
            row=1, column=0, sticky="e", padx=8, pady=6
        )
        self.text_var = tb.StringVar()
        tb.Entry(self, textvariable=self.text_var, width=25).grid(
            row=1, column=1, padx=8, pady=6
        )

        btn_frame = tb.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        tb.Button(
            btn_frame, text="Insert", command=self._insert, bootstyle="primary"
        ).pack(side=tk.LEFT, padx=3)
        tb.Button(
            btn_frame, text="Cancel", command=self.destroy, bootstyle="secondary"
        ).pack(side=tk.LEFT, padx=3)

    def _insert(self) -> None:
        hid = self.id_var.get().strip()
        text = self.text_var.get().strip()
        if hid:
            label = text or "link"
            self.result = f"[{label}](#{hid})"
        self.destroy()


# ---------------------------------------------------------------------------
# Line-number canvas
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Main Editor Application
# ---------------------------------------------------------------------------


class MarkEditor(tb.App):
    def __init__(self) -> None:
        super().__init__(themename="one-light")
        self.title(f"{__app_name__} - New File")
        self.geometry("1000x700")
        self.minsize(600, 400)

        # ── state ──────────────────────────────────────────────
        self.current_file: Optional[str] = None
        self.is_modified = False
        self._zoom_level = 0

        # ── fonts ──────────────────────────────────────────────
        self.editor_font = resolve_font(
            "Mono", "Fira Code", "Liberation Mono", "Courier", 14
        )
        self.body_font = resolve_font(
            "Serif", "Noto Serif", "Liberation Serif", "Times", 14
        )
        self.code_font = resolve_font(
            "Mono", "Fira Code", "Liberation Mono", "Courier", 14
        )
        self.interface_font = resolve_font(
            "Sans", "Noto Sans", "Liberation Sans", "Arial", 10
        )

        # ── layout ─────────────────────────────────────────────
        self._build_menu()
        self._build_panels()
        self._build_statusbar()

        # ── window icon ────────────────────────────────────────
        for name in ("images/mark_editor.png", "images/mark_editor.svg"):
            icon_path = resource_path(name)
            if os.path.exists(icon_path) and HAS_PILLOW:
                try:
                    img = Image.open(icon_path)
                    photo = ImageTk.PhotoImage(img)
                    self.iconphoto(True, photo)
                    self._icon_photo = photo
                except Exception:
                    pass
                break

        # ── key bindings ───────────────────────────────────────
        self._bind_shortcuts()

        # ── refresh timer ──────────────────────────────────────
        self._refresh_after_id: Optional[str] = None
        self._preview_images: list = []
        self._preview_tables: list[tk.Widget] = []

        # ── protocol ───────────────────────────────────────────
        self.on_close(self._on_quit)

        # ── equalise panels on first show ──────────────────────
        self.after(1, self._equalize_panes)

    # ═══════════════════════════════════════════════════════════
    # Menu bar
    # ═══════════════════════════════════════════════════════════

    def _build_menu(self) -> None:
        menubar = tb.Menu(self)
        self.config(menu=menubar)

        # ── File ──
        file_menu = tb.Menu(menubar, tearoff=False)
        file_menu.add_command(
            label="New File", accelerator="Ctrl+N", command=self._on_new
        )
        file_menu.add_separator()
        file_menu.add_command(label="Open", accelerator="Ctrl+O", command=self._on_open)
        file_menu.add_command(
            label="Reopen", accelerator="Ctrl+Shift+O", command=self._on_reopen
        )
        file_menu.add_separator()
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self._on_save)
        file_menu.add_command(
            label="Save As", accelerator="Ctrl+Shift+S", command=self._on_save_as
        )
        file_menu.add_command(
            label="Convert", accelerator="Ctrl+E", command=self._on_convert
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
        edit_menu.add_command(
            label="Paste", accelerator="Ctrl+V", command=self._on_paste
        )
        edit_menu.add_separator()
        edit_menu.add_command(label="Find", accelerator="Ctrl+F", command=self._on_find)
        edit_menu.add_command(
            label="Replace", accelerator="Ctrl+R", command=self._on_replace
        )
        edit_menu.add_command(
            label="Replace All",
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
            label="Header ID", accelerator="Ctrl+H", command=self._on_header_id
        )
        format_menu.add_command(
            label="Header Link",
            accelerator="Ctrl+Shift+H",
            command=self._on_header_link,
        )
        format_menu.add_command(
            label="Hyperlink", accelerator="Ctrl+L", command=self._on_hyperlink
        )
        format_menu.add_command(
            label="Footnote", accelerator="Ctrl+Shift+U", command=self._on_footnote
        )
        format_menu.add_separator()
        format_menu.add_command(
            label="Furigana", accelerator="Ctrl+Shift+J", command=self._on_furigana
        )
        format_menu.add_command(
            label="Date and Time",
            accelerator="Ctrl+Shift+D",
            command=self._on_date_time,
        )
        format_menu.add_command(
            label="Special Mark",
            accelerator="Ctrl+Shift+L",
            command=self._on_special_mark,
        )
        format_menu.add_separator()
        format_menu.add_command(
            label="Clear Formatting",
            accelerator="Ctrl+Shift+F",
            command=self._on_clear_formatting,
        )
        menubar.add_cascade(label="Format", menu=format_menu)

        # ── Paragraph ──
        para_menu = tb.Menu(menubar, tearoff=False)
        for i in range(1, 7):
            para_menu.add_command(
                label=f"Heading {i}",
                accelerator=f"Alt+Ctrl+{i}",
                command=lambda level=i: self._on_heading(level),
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
        para_menu.add_separator()
        para_menu.add_command(
            label="Code Block", accelerator="Ctrl+Shift+K", command=self._on_code_block
        )
        para_menu.add_command(
            label="Blockquote", accelerator="Ctrl+Shift+Q", command=self._on_blockquote
        )
        para_menu.add_command(
            label="Table", accelerator="Ctrl+T", command=self._on_table
        )
        para_menu.add_command(
            label="Image", accelerator="Ctrl+Shift+I", command=self._on_image
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
            label="Comment", accelerator="Ctrl+M", command=self._on_comment
        )
        menubar.add_cascade(label="Paragraph", menu=para_menu)

        # ── View ──
        view_menu = tb.Menu(menubar, tearoff=False)
        view_menu.add_command(
            label="Toggle Theme",
            accelerator="Ctrl+Shift+T",
            command=self._on_toggle_theme,
        )
        change_menu = tb.Menu(view_menu, tearoff=False)
        for theme in (
            "bootstrap",
            "catppuccin",
            "dracula",
            "everforest",
            "gruvbox",
            "minty",
            "nord",
            "one",
            "pulse",
            "pydata",
            "sandstone",
            "solarized",
            "tokyo-night",
            "united",
            "vapor",
        ):
            change_menu.add_command(
                label=theme.replace("-", " ").title(),
                command=lambda t=theme: self._on_change_theme(t),
            )
        view_menu.add_cascade(label="Change Theme", menu=change_menu)
        view_menu.add_separator()
        view_menu.add_command(
            label="Zoom In", accelerator="Ctrl++", command=self._on_zoom_in
        )
        view_menu.add_command(
            label="Zoom Out", accelerator="Ctrl+-", command=self._on_zoom_out
        )
        view_menu.add_separator()
        view_menu.add_command(
            label="Refresh", accelerator="Ctrl+Shift+E", command=self._on_refresh
        )
        menubar.add_cascade(label="View", menu=view_menu)

        # ── Help ──
        help_menu = tb.Menu(menubar, tearoff=False)
        help_menu.add_command(label="Markdown", command=self._on_help_markdown)
        help_menu.add_command(label="About Editor", command=self._on_help_about)
        menubar.add_cascade(label="Help", menu=help_menu)

    # ═══════════════════════════════════════════════════════════
    # Layout — panels + status bar
    # ═══════════════════════════════════════════════════════════

    def _build_panels(self) -> None:
        self._paned = tb.Panedwindow(self, orient=tk.HORIZONTAL)
        self._paned.pack(fill=tk.BOTH, expand=True)

        # ── left panel: editing ──
        left_frame = tb.Frame(self._paned)
        self._editor_vbar = tb.Scrollbar(left_frame, orient=tk.VERTICAL)
        self._editor = tk.Text(
            left_frame,
            font=self.editor_font,
            wrap=tk.WORD,
            undo=True,
            padx=8,
            pady=8,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#ccc",
            yscrollcommand=self._editor_vbar.set,
        )
        self._editor_vbar.config(command=self._editor.yview)
        self._editor_vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._editor.pack(fill=tk.BOTH, expand=True)

        self._editor.bind("<<Modified>>", self._on_editor_modified)
        self._editor.bind("<KeyRelease>", self._schedule_refresh)
        self._editor.bind("<ButtonRelease-1>", self._schedule_refresh)
        self._editor.bind("<ButtonRelease-1>", self._update_status, add=True)

        self._paned.add(left_frame, weight=1)

        # ── right panel: quick view ──
        right_frame = tb.Frame(self._paned)
        self._preview_vbar = tb.Scrollbar(right_frame, orient=tk.VERTICAL)
        self._preview = tk.Text(
            right_frame,
            font=self.body_font,
            wrap=tk.WORD,
            state=tk.DISABLED,
            padx=8,
            pady=8,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#ccc",
            cursor="arrow",
            bg="#ffffff",
            fg="#212529",
            yscrollcommand=self._preview_vbar.set,
        )
        self._preview_vbar.config(command=self._preview.yview)
        self._preview_vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._preview.pack(fill=tk.BOTH, expand=True)
        self._preview._tb_no_autostyle = True
        self._configure_preview_tags()
        self._paned.add(right_frame, weight=1)

    def _build_statusbar(self) -> None:
        self._status_var = tb.StringVar(value="Ln 1, Col 1")
        status = tb.Label(
            self,
            textvariable=self._status_var,
            anchor=tk.E,
            padding=(10, 2),
            font=self.interface_font,
            bootstyle="inverse-secondary",
        )
        status.pack(side=tk.BOTTOM, fill=tk.X)

    def _equalize_panes(self) -> None:
        self.update_idletasks()
        w = self.winfo_width()
        if w > 1:
            self._paned.sashpos(0, w // 2)

    # ═══════════════════════════════════════════════════════════
    # Preview tag configuration
    # ═══════════════════════════════════════════════════════════

    def _configure_preview_tags(self) -> None:
        pv = self._preview

        gen_sans, user_sans = "Arial", "Noto Sans"
        gen_serif, user_serif = "Times", "Noto Serif"
        gen_mono, user_mono = "Courier", "Fira Code"

        sans = user_sans if font_installed(user_sans) else gen_sans
        serif = user_serif if font_installed(user_serif) else gen_serif
        mono = user_mono if font_installed(user_mono) else gen_mono

        pv.tag_configure("p", font=(serif, 14), spacing1=4, spacing3=4)
        pv.tag_configure("bold", font=(serif, 14, "bold"))
        pv.tag_configure("bold_sans", font=(sans, 14, "bold"))
        pv.tag_configure("bold_mono", font=(mono, 13, "bold"))
        pv.tag_configure("italic", font=(serif, 14, "italic"))
        pv.tag_configure("italic_sans", font=(sans, 14, "italic"))
        pv.tag_configure("italic_mono", font=(mono, 13, "italic"))
        pv.tag_configure("bold_italic", font=(serif, 14, "bold italic"))
        pv.tag_configure("bold_italic_sans", font=(sans, 14, "bold italic"))
        pv.tag_configure("bold_italic_mono", font=(mono, 13, "bold italic"))
        pv.tag_configure("u", underline=True)
        pv.tag_configure("del", overstrike=True)
        pv.tag_configure("mark", background="#fff3cd")
        pv.tag_configure("code", font=(mono, 13), background="#f8f9fa")
        pv.tag_configure("code_header", font=(mono, 13, "bold"), background="#e9ecef")
        pv.tag_configure(
            "pre",
            font=(mono, 13),
            background="#f8f9fa",
            spacing1=4,
            spacing3=4,
            lmargin1=20,
            lmargin2=20,
        )
        pv.tag_configure(
            "blockquote",
            font=(serif, 14, "italic"),
            lmargin1=30,
            lmargin2=30,
            foreground="#6c757d",
        )
        pv.tag_configure("link", foreground="#0d6efd", underline=True)
        pv.tag_configure("ul", lmargin1=20, lmargin2=20)
        pv.tag_configure("ol", lmargin1=20, lmargin2=20)
        pv.tag_configure("table", font=(mono, 12), spacing1=2, spacing3=2)
        pv.tag_configure("hr", foreground="#dee2e6")
        pv.tag_configure("img", font=(sans, 14, "bold"), foreground="#adb5bd")

        for level in range(1, 7):
            sz = {1: 24, 2: 22, 3: 20, 4: 18, 5: 16, 6: 14}[level]
            pv.tag_configure(
                f"h{level}", font=(sans, sz, "bold"), spacing1=8, spacing3=4
            )

        pv.tag_configure("sup", font=(serif, 10), offset=6)
        pv.tag_configure("sub", font=(serif, 10), offset=-4)
        pv.tag_configure("ruby_rt", font=(serif, 11), spacing3=4)

    # ═══════════════════════════════════════════════════════════
    # Shortcut bindings
    # ═══════════════════════════════════════════════════════════

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
        self.bind_all("<Control-Shift-n>", lambda e: self._on_next_theme())
        self.bind_all("<Control-Shift-u>", lambda e: self._on_footnote())
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
        self.bind_all("<Control-Shift-k>", lambda e: self._on_code_block())
        self.bind_all("<Control-Shift-q>", lambda e: self._on_blockquote())
        self.bind_all("<Control-t>", lambda e: self._on_table())
        self.bind_all("<Control-Shift-i>", lambda e: self._on_image())
        self.bind_all("<Control-backslash>", lambda e: self._on_line_break())
        self.bind_all("<Control-underscore>", lambda e: self._on_horizontal_rule())
        self.bind_all("<Tab>", lambda e: self._on_add_indent())
        self.bind_all("<Shift-Tab>", lambda e: self._on_remove_indent())
        self.bind_all("<Control-m>", lambda e: self._on_comment())

        self.bind_all("<Control-equal>", lambda e: self._on_zoom_in())
        self.bind_all("<Control-plus>", lambda e: self._on_zoom_in())
        self.bind_all("<Control-minus>", lambda e: self._on_zoom_out())
        self.bind_all("<Control-Shift-e>", lambda e: self._on_refresh())

    # ═══════════════════════════════════════════════════════════
    # Title bar
    # ═══════════════════════════════════════════════════════════

    def _update_title(self) -> None:
        symbol = "*" if self.is_modified else ""
        name = self.current_file or "New File"
        self.title(f"{__app_name__} - {symbol}{name}")

    # ═══════════════════════════════════════════════════════════
    # Status bar
    # ═══════════════════════════════════════════════════════════

    def _update_status(self, _event=None) -> None:
        try:
            idx = self._editor.index(tk.INSERT)
            line, col = idx.split(".")
            self._status_var.set(f"Ln {line}, Col {int(col) + 1}")
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════
    # Editor change tracking
    # ═══════════════════════════════════════════════════════════

    def _on_editor_modified(self, _event=None) -> None:
        if self._editor.edit_modified():
            self.is_modified = True
            self._update_title()
            self._editor.edit_modified(False)

    def _schedule_refresh(self, _event=None) -> None:
        self._update_status()
        if self._refresh_after_id:
            self.after_cancel(self._refresh_after_id)
        self._refresh_after_id = self.after(300, self._refresh_preview)

    @staticmethod
    def _split_lists(text: str) -> str:
        return re.sub(
            r"(^[ \t]*(?:[-*+]|\d+\.).*\n)\n+(?=[ \t]*(?:[-*+]|\d+\.))",
            r"\1<!-- -->\n",
            text,
            flags=re.MULTILINE,
        )

    # ═══════════════════════════════════════════════════════════
    # Preview rendering
    # ═══════════════════════════════════════════════════════════

    def _refresh_preview(self) -> None:
        self._refresh_after_id = None
        text = self._editor.get("1.0", tk.END).strip()
        if not text:
            return

        text = self._split_lists(text)
        html = markdown.markdown(
            text,
            extensions=[
                "fenced_code",
                "pymdownx.caret",
                "pymdownx.tilde",
                "pymdownx.mark",
                "pymdownx.smartsymbols",
                "footnotes",
                "tables",
                "attr_list",
                TableExtension(use_align_attribute=True),
            ],
            extension_configs={
                "pymdownx.caret": {},
                "pymdownx.tilde": {},
            },
        )

        pv = self._preview
        pv.config(state=tk.NORMAL)
        for w in self._preview_tables:
            w.destroy()
        self._preview_tables.clear()
        pv.delete("1.0", tk.END)

        base_dir = (
            os.path.dirname(self.current_file) if self.current_file else os.getcwd()
        )
        self._preview_images = []
        renderer = TkHTMLRenderer(
            pv, self.body_font, ("Sans", "Noto Sans"), self.code_font, base_dir=base_dir
        )
        renderer.feed(html)
        renderer.close()
        self._preview_images = renderer._image_refs
        self._preview_tables = renderer._table_refs

        if text and not pv.get("1.0", tk.END).strip():
            pv.insert(tk.END, text)

        pv.config(state=tk.DISABLED)

    # ═══════════════════════════════════════════════════════════
    # File operations
    # ═══════════════════════════════════════════════════════════

    def _check_save(self) -> bool:
        """If modified, ask to save. Returns True to proceed, False to cancel."""
        if not self.is_modified:
            return True
        resp = Messagebox.yesnocancel(
            "Save the opened file?",
            "Save?",
            parent=self,
        )
        if resp == "Yes":  # Yes → save and proceed
            self._on_save()
            return True
        if resp == "No":  # No → proceed without saving
            return True
        return False  # Cancel → abort

    def _on_new(self) -> None:
        if not self._check_save():
            return
        self._editor.delete("1.0", tk.END)
        self.current_file = None
        self.is_modified = False
        self._update_title()
        self._refresh_preview()

    def _on_open(self) -> None:
        if not self._check_save():
            return
        path = Querybox.get_open_filename(
            parent=self,
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            Messagebox.show_error(f"Could not open file:\n{e}", "Error", parent=self)
            return
        self._editor.delete("1.0", tk.END)
        self._editor.insert("1.0", content)
        self.current_file = path
        self.is_modified = False
        self._editor.edit_modified(False)
        self._update_title()
        self._refresh_preview()

    def _on_reopen(self) -> None:
        if not self.current_file:
            return
        if not self._check_save():
            return
        try:
            with open(self.current_file, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            Messagebox.show_error(f"Could not reopen file:\n{e}", "Error", parent=self)
            return
        self._editor.delete("1.0", tk.END)
        self._editor.insert("1.0", content)
        self.is_modified = False
        self._editor.edit_modified(False)
        self._update_title()
        self._refresh_preview()

    def _on_save(self) -> bool:
        if self.current_file:
            try:
                content = self._editor.get("1.0", tk.END)
                with open(self.current_file, "w", encoding="utf-8") as f:
                    f.write(content)
                self.is_modified = False
                self._editor.edit_modified(False)
                self._update_title()
                return True
            except Exception as e:
                Messagebox.show_error(
                    f"Could not save file:\n{e}", "Error", parent=self
                )
                return False
        return self._on_save_as()

    def _on_save_as(self) -> bool:
        path = Querybox.get_save_filename(
            parent=self,
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
        )
        if not path:
            return False
        self.current_file = path
        return self._on_save()

    def _on_convert(self) -> None:
        text = self._editor.get("1.0", tk.END)
        if not text.strip():
            Messagebox.show_info("Nothing to convert.", "Convert", parent=self)
            return

        path = Querybox.get_save_filename(
            parent=self,
            defaultextension=".txt",
            filetypes=[
                ("Plain text", "*.txt"),
                ("PDF", "*.pdf"),
            ],
        )
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()

        if ext == ".txt":
            try:
                html = markdown.markdown(
                    self._split_lists(text),
                    extensions=[
                        "pymdownx.caret",
                        "pymdownx.tilde",
                        "pymdownx.mark",
                        "pymdownx.smartsymbols",
                        "footnotes",
                        "tables",
                        "attr_list",
                        TableExtension(use_align_attribute=True),
                    ],
                )
                plain = re.sub(r"<[^>]+>", "", html)
                plain = html.unescape(plain) if hasattr(html, "unescape") else plain
                with open(path, "w", encoding="utf-8") as f:
                    f.write(plain)
                Messagebox.show_info("Saved as plain text.", "Convert", parent=self)
            except Exception as e:
                Messagebox.show_error(f"Export failed:\n{e}", "Error", parent=self)

        elif ext == ".pdf":
            if not HAS_PYPANDOC:
                Messagebox.show_error(
                    "pypandoc is required for PDF export.\n"
                    "Install it with: pip install pypandoc",
                    "Error",
                    parent=self,
                )
                return
            try:
                html = markdown.markdown(
                    self._split_lists(text),
                    extensions=[
                        "fenced_code",
                        "pymdownx.caret",
                        "pymdownx.tilde",
                        "pymdownx.mark",
                        "pymdownx.smartsymbols",
                        "footnotes",
                        "tables",
                        "attr_list",
                        TableExtension(use_align_attribute=True),
                    ],
                )
                html = html.replace("&#8617;", "")
                html = re.sub(
                    r"<h6([^>]*)>(.*?)</h6>",
                    r"<p\1><strong>\2</strong></p>",
                    html,
                )
                html = re.sub(
                    r"<ruby>([^<]+)<rt>([^<]+)</rt></ruby>",
                    r"\1【\2】",
                    html,
                )
                html = re.sub(
                    r'<pre><code class="language-([^"]+)">',
                    r'<p>§LANG§\1§</p><pre><code class="language-\1">',
                    html,
                )
                html = re.sub(
                    r"<th([^>]*)>(.*?)</th>",
                    r"<th\1><strong>\2</strong></th>",
                    html,
                )
                base = (
                    os.path.dirname(self.current_file)
                    if self.current_file
                    else os.getcwd()
                )

                def _resolve_img(m):
                    src = m.group(1)
                    full = os.path.join(base, src) if not os.path.isabs(src) else src
                    if os.path.exists(full):
                        return m.group(0).replace(f'src="{src}"', f'src="{full}"')
                    return f"<p>[{src}]</p>"

                html = re.sub(
                    r'<img\s+[^>]*?src="([^"]*?)"[^>]*?>',
                    _resolve_img,
                    html,
                )
                tex = pypandoc.convert_text(
                    html,
                    "latex",
                    format="html",
                    extra_args=[
                        "--standalone",
                        "--listings",
                        "-V",
                        "mainfont=Noto Sans",
                        "-V",
                        "CJKmainfont=Noto Sans CJK JP",
                        "-V",
                        "colorlinks=true",
                    ],
                )
                tex_path = path.replace(".pdf", ".tex")
                tex = tex.replace(
                    "\\begin{document}",
                    "\\usepackage{ruby}\n"
                    "\\renewcommand{\\rubysize}{0.65}\n"
                    "\\renewcommand{\\rubysep}{0.8ex}\n"
                    "\\usepackage{xcolor}\n"
                    "\\newcommand{\\codeheader}[1]{\\par\\noindent\\colorbox{gray!15}"
                    "{\\parbox{\\dimexpr\\linewidth-2\\fboxsep\\relax}"
                    "{\\small\\ttfamily\\bfseries\\ \\ #1}}\\par"
                    "\\vspace{-0.5em}}\n"
                    "\\lstset{backgroundcolor=\\color{gray!5},frame=single,"
                    "framerule=0pt,basicstyle=\\ttfamily\\small,breaklines=true}\n"
                    "\\let\\oldquote\\quote\\let\\endoldquote\\endquote\n"
                    "\\renewenvironment{quote}{\\oldquote\\itshape}{\\endoldquote}\n"
                    "\\begin{document}",
                )
                tex = re.sub(
                    r"§LANG§(\w+)§\n*\n*\\begin\{lstlisting\}",
                    r"\\codeheader{\1}\n\\begin{lstlisting}",
                    tex,
                )

                # Replace 【reading】 markers with \ruby{base}{reading}
                parts = tex.split("\\begin{document}", 1)
                if len(parts) == 2:
                    body = parts[1]
                    result = []
                    i = 0
                    while i < len(body):
                        idx = body.find("\u3010", i)
                        if idx == -1:
                            result.append(body[i:])
                            break
                        end = body.find("\u3011", idx)
                        if end == -1:
                            result.append(body[idx:])
                            break
                        reading = body[idx + 1 : end]
                        base_end = idx
                        base_start = base_end
                        while base_start > 0 and base_end - base_start < 30:
                            ch = body[base_start - 1]
                            if ch in "\u3010\u3011\n{}":
                                break
                            base_start -= 1
                        base_text = body[base_start:base_end].strip()
                        result.append(body[i:base_start])
                        result.append("\\ruby{" + base_text + "}{" + reading + "}")
                        i = end + 1
                    tex = parts[0] + "\\begin{document}" + "".join(result)
                else:
                    tex = tex.replace("\u3010", "\\ruby{").replace("\u3011", "}")
                with open(tex_path, "w", encoding="utf-8") as f:
                    f.write(tex)
                for _ in range(2):
                    subprocess.run(
                        [
                            "xelatex",
                            "-interaction=nonstopmode",
                            "-output-directory",
                            os.path.dirname(tex_path) or ".",
                            tex_path,
                        ],
                        capture_output=True,
                        timeout=120,
                    )
                pdf_path = tex_path.replace(".tex", ".pdf")
                if os.path.exists(pdf_path) and pdf_path != path:
                    import shutil

                    shutil.move(pdf_path, path)
                out_dir = os.path.dirname(tex_path) or "."
                base = os.path.splitext(os.path.basename(tex_path))[0]
                for ext in (".tex", ".aux", ".log"):
                    f = os.path.join(out_dir, base + ext)
                    if os.path.exists(f):
                        os.remove(f)
                try:
                    Messagebox.show_info("Saved as PDF.", "Convert", parent=self)
                except tk.TclError:
                    Messagebox.show_info("Saved as PDF.", "Convert")
            except Exception as e:
                try:
                    Messagebox.show_error(
                        f"PDF export failed:\n{e}", "Error", parent=self
                    )
                except tk.TclError:
                    Messagebox.show_error(f"PDF export failed:\n{e}", "Error")

    def _on_quit(self) -> None:
        if not self._check_save():
            return
        self.destroy()

    # ═══════════════════════════════════════════════════════════
    # Edit operations
    # ═══════════════════════════════════════════════════════════

    def _on_undo(self) -> None:
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
        self.clipboard_clear()
        try:
            text = self._editor.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.clipboard_append(text)
            self._editor.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            pass

    def _on_copy(self) -> None:
        self.clipboard_clear()
        try:
            text = self._editor.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.clipboard_append(text)
        except tk.TclError:
            pass

    def _on_paste(self) -> None:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return
        try:
            self._editor.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            pass
        self._editor.insert(tk.INSERT, text)

    def _on_select_all(self) -> None:
        self._editor.tag_add(tk.SEL, "1.0", tk.END)
        self._editor.mark_set(tk.INSERT, "1.0")
        self._editor.see(tk.INSERT)

    def _on_remove_selection(self) -> None:
        self._editor.tag_remove(tk.SEL, "1.0", tk.END)

    def _on_line_up(self) -> None:
        try:
            cur = self._editor.index(tk.INSERT)
            line = int(cur.split(".")[0])
            if line <= 1:
                return
            prev_start = f"{line - 1}.0"
            cur_end = f"{line + 1}.0"
            pair = self._editor.get(prev_start, cur_end)
            lines = pair.splitlines(True)
            if len(lines) < 2:
                return
            swapped = lines[1] + lines[0]
            self._editor.delete(prev_start, cur_end)
            self._editor.insert(prev_start, swapped)
            self._editor.mark_set(tk.INSERT, f"{line - 1}.{cur.split('.')[1]}")
        except Exception:
            pass

    def _on_line_down(self) -> None:
        try:
            cur = self._editor.index(tk.INSERT)
            line = int(cur.split(".")[0])
            total = int(self._editor.index(tk.END).split(".")[0])
            if line >= total - 1:
                return
            cur_start = f"{line}.0"
            next_end = f"{line + 2}.0" if line + 1 < total - 1 else tk.END
            pair = self._editor.get(cur_start, next_end)
            lines = pair.splitlines(True)
            if len(lines) < 2:
                return
            swapped = lines[1] + lines[0]
            self._editor.delete(cur_start, next_end)
            self._editor.insert(cur_start, swapped)
            self._editor.mark_set(tk.INSERT, f"{line + 1}.{cur.split('.')[1]}")
        except Exception:
            pass

    def _on_delete_line(self) -> None:
        try:
            cur = self._editor.index(tk.INSERT)
            line = int(cur.split(".")[0])
            total = int(self._editor.index(tk.END).split(".")[0]) - 1
            if line < total:
                self._editor.delete(f"{line}.0", f"{line + 1}.0")
            elif total > 0:
                self._editor.delete(f"{line - 1}.0", tk.END)
        except Exception:
            pass

    # ── Find / Replace ──

    def _on_find(self) -> None:
        FindDialog(self, self._editor)

    def _on_replace(self) -> None:
        ReplaceDialog(self, self._editor)

    def _on_replace_all(self) -> None:
        ReplaceDialog(self, self._editor)

    # ═══════════════════════════════════════════════════════════
    # Format operations
    # ═══════════════════════════════════════════════════════════

    def _wrap_selection(self, wrapper: str) -> None:
        try:
            sel = self._editor.get(tk.SEL_FIRST, tk.SEL_LAST)
            start = self._editor.index(tk.SEL_FIRST)
            end = self._editor.index(tk.SEL_LAST)
            self._editor.replace(start, end, f"{wrapper}{sel}{wrapper}")
        except tk.TclError:
            pass

    def _wrap_prefix(self, prefix: str) -> None:
        try:
            sel = self._editor.get(tk.SEL_FIRST, tk.SEL_LAST)
            start = self._editor.index(tk.SEL_FIRST)
            end = self._editor.index(tk.SEL_LAST)
            self._editor.replace(start, end, f"{prefix}{sel}")
        except tk.TclError:
            pass

    def _on_header_id(self) -> None:
        cur = self._editor.index(tk.INSERT)
        line = cur.split(".")[0]
        text = self._editor.get(f"{line}.0", f"{line}.end")
        match = re.match(r"^(#+)\s+(.*)", text)
        if not match:
            Messagebox.show_info(
                "Cursor must be on a heading line.", "Header ID", parent=self
            )
            return
        id_str = Querybox.get_string("Enter custom ID:", "Header ID", parent=self)
        if id_str:
            self._editor.insert(f"{line}.end", f" {{#{id_str}}}")

    def _on_header_link(self) -> None:
        dlg = HeaderLinkDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self._editor.insert(tk.INSERT, dlg.result)

    def _on_hyperlink(self) -> None:
        text = Querybox.get_string("Link text:", "Hyperlink", parent=self)
        if not text:
            return
        url = Querybox.get_string("URL:", "Hyperlink", parent=self)
        if url:
            result = f"[{text}]({url})"
            try:
                self._editor.delete(tk.SEL_FIRST, tk.SEL_LAST)
            except tk.TclError:
                pass
            self._editor.insert(tk.INSERT, result)

    def _on_footnote(self) -> None:
        ref = Querybox.get_string("Footnote reference/name:", "Footnote", parent=self)
        if not ref:
            return
        self._editor.insert(tk.INSERT, f"[^{ref}]")
        self._editor.insert(tk.END, f"\n\n[^{ref}]: ")

    def _on_furigana(self) -> None:
        dlg = FuriganaDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self._editor.insert(tk.INSERT, dlg.result)

    def _on_date_time(self) -> None:
        now = datetime.now()
        fmt = Querybox.get_string(
            "Format: date, time, or date/time?",
            "Date and Time",
            parent=self,
            initialvalue="date/time",
        )
        if not fmt:
            return
        fmt_lower = fmt.lower()
        if "date" in fmt_lower and "time" in fmt_lower:
            result = now.strftime("%Y-%m-%d %H:%M")
        elif "time" in fmt_lower:
            result = now.strftime("%H:%M")
        else:
            result = now.strftime("%Y-%m-%d")
        self._editor.insert(tk.INSERT, result)

    def _on_special_mark(self) -> None:
        self._editor.insert(tk.INSERT, "\\")

    def _on_clear_formatting(self) -> None:
        try:
            sel = self._editor.get(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            return

        patterns = [
            (r"\*\*(.+?)\*\*", r"\1"),
            (r"\*(.+?)\*", r"\1"),
            (r"\^\^(.+?)\^\^", r"\1"),
            (r"~~(.+?)~~", r"\1"),
            (r"`(.+?)`", r"\1"),
            (r"==(.+?)==", r"\1"),
            (r"~(.+?)~", r"\1"),
            (r"\^([^^]+)", r"\1"),
            (r"\[(.+?)\]\(.+?\)", r"\1"),
            (r"!\[(.+?)\]\(.+?\)", r"\1"),
            (r"\[(.+?)\]\[\]", r"\1"),
        ]
        cleaned = sel
        for pattern, repl in patterns:
            cleaned = re.sub(pattern, repl, cleaned)

        lines_out = []
        for line in cleaned.split("\n"):
            line = re.sub(r"^#+\s*", "", line)
            line = re.sub(r"^>\s*", "", line)
            line = re.sub(r"^[\*\-\+]\s+", "", line)
            line = re.sub(r"^\d+\.\s+", "", line)
            lines_out.append(line)
        cleaned = "\n".join(lines_out)

        start = self._editor.index(tk.SEL_FIRST)
        end = self._editor.index(tk.SEL_LAST)
        self._editor.replace(start, end, cleaned)

    # ═══════════════════════════════════════════════════════════
    # Paragraph operations
    # ═══════════════════════════════════════════════════════════

    def _get_current_line_text(self) -> str:
        cur = self._editor.index(tk.INSERT)
        line = cur.split(".")[0]
        return self._editor.get(f"{line}.0", f"{line}.end")

    def _replace_current_line(self, new_text: str) -> None:
        cur = self._editor.index(tk.INSERT)
        line = cur.split(".")[0]
        self._editor.delete(f"{line}.0", f"{line}.end")
        self._editor.insert(f"{line}.0", new_text)

    def _on_heading(self, level: int) -> None:
        prefix = "#" * level
        text = self._get_current_line_text()
        text = re.sub(r"^#*\s*", "", text)
        self._replace_current_line(f"{prefix} {text}")

    def _on_paragraph(self) -> None:
        self._editor.insert(tk.INSERT, "\n\n")
        self._editor.mark_set(tk.INSERT, f"{tk.INSERT} linestart")

    def _add_blank_line_before_if_needed(self) -> None:
        cur = self._editor.index(tk.INSERT)
        line_num = int(cur.split(".")[0])
        if line_num > 1:
            prev = self._editor.get(f"{line_num - 1}.0", f"{line_num - 1}.end")
            if prev.strip():
                self._editor.insert(f"{line_num}.0", "\n")

    def _on_ordered_list(self) -> None:
        text = self._get_current_line_text()
        if re.match(r"^\d+\.\s+", text):
            return
        text = re.sub(r"^[*\-\+]\s+", "", text)
        self._add_blank_line_before_if_needed()
        self._replace_current_line(f"1. {text}")

    def _on_unordered_list(self) -> None:
        text = self._get_current_line_text()
        if re.match(r"^[\*\-\+]\s+", text):
            return
        text = re.sub(r"^\d+\.\s+", "", text)
        self._add_blank_line_before_if_needed()
        self._replace_current_line(f"* {text}")

    def _on_code_block(self) -> None:
        lang = Querybox.get_string(
            "Programming language (optional):", "Code Block", parent=self
        )
        if lang is None:
            return
        lang_str = lang or ""
        try:
            sel = self._editor.get(tk.SEL_FIRST, tk.SEL_LAST)
            start = self._editor.index(tk.SEL_FIRST)
            end = self._editor.index(tk.SEL_LAST)
            self._editor.replace(start, end, f"```{lang_str}\n{sel}\n```")
        except tk.TclError:
            cur = self._editor.index(tk.INSERT)
            insert_text = f"\n```{lang_str}\n\n```\n"
            self._editor.insert(cur, insert_text)

    def _on_blockquote(self) -> None:
        text = self._get_current_line_text()
        if text.startswith(">"):
            return
        self._replace_current_line(f"> {text}")

    def _on_table(self) -> None:
        dlg = TableDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self._editor.insert(tk.INSERT, "\n" + dlg.result + "\n")

    def _on_image(self) -> None:
        alt = Querybox.get_string("Alt text:", "Image", parent=self)
        alt = alt or ""
        path = Querybox.get_open_filename(
            parent=self,
            title="Select image file",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.gif *.svg *.bmp"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self._editor.insert(tk.INSERT, f"![{alt}]({path})")

    def _on_line_break(self) -> None:
        self._editor.insert(tk.INSERT, "  \n")

    def _on_horizontal_rule(self) -> None:
        self._editor.insert(tk.INSERT, "\n***\n")

    def _on_add_indent(self) -> None:
        cur = self._editor.index(tk.INSERT)
        line = cur.split(".")[0]
        self._editor.insert(f"{line}.0", "  ")

    def _on_remove_indent(self) -> None:
        cur = self._editor.index(tk.INSERT)
        line = cur.split(".")[0]
        text = self._editor.get(f"{line}.0", f"{line}.0+2c")
        if text == "  ":
            self._editor.delete(f"{line}.0", f"{line}.0+2c")
        elif text and text[0] == " ":
            self._editor.delete(f"{line}.0", f"{line}.0+1c")

    def _on_comment(self) -> None:
        try:
            sel = self._editor.get(tk.SEL_FIRST, tk.SEL_LAST)
            start = self._editor.index(tk.SEL_FIRST)
            end = self._editor.index(tk.SEL_LAST)
            self._editor.replace(start, end, f"<!-- {sel} -->")
            self._editor.mark_set(tk.INSERT, f"{start}+{len('<!-- ')}c+{len(sel)}c")
        except tk.TclError:
            self._editor.insert(tk.INSERT, "<!--  -->")
            self._editor.mark_set(tk.INSERT, "insert-4c")

    # ═══════════════════════════════════════════════════════════
    # View operations
    # ═══════════════════════════════════════════════════════════

    def _adjust_panel_font(self, delta: int) -> None:
        for font_attr in ("body_font", "code_font"):
            font: Font = getattr(self, font_attr)
            new_size = max(6, font.actual("size") + delta)
            font.config(size=new_size)

        self._configure_preview_tags()

    def _on_zoom_in(self) -> None:
        self._adjust_panel_font(2)

    def _on_zoom_out(self) -> None:
        self._adjust_panel_font(-2)

    def _on_refresh(self) -> None:
        self._refresh_preview()

    def _on_toggle_theme(self) -> None:
        self.toggle_theme()

    def _on_change_theme(self, base: str) -> None:
        self.style.theme_use(f"{base}-light")

    def _on_next_theme(self) -> None:
        bases = [
            "bootstrap",
            "catppuccin",
            "dracula",
            "everforest",
            "gruvbox",
            "minty",
            "nord",
            "one",
            "pulse",
            "pydata",
            "sandstone",
            "solarized",
            "tokyo-night",
            "united",
            "vapor",
        ]
        current = self.style.theme
        for i, b in enumerate(bases):
            if current.startswith(b):
                next_base = bases[(i + 1) % len(bases)]
                self.style.theme_use(f"{next_base}-light")
                return

    # ═══════════════════════════════════════════════════════════
    # Help operations
    # ═══════════════════════════════════════════════════════════

    def _on_help_markdown(self) -> None:
        webbrowser.open("https://daringfireball.net/projects/markdown/")

    def _on_help_about(self) -> None:
        Messagebox.show_info(
            f"{__app_name__}, version {__version__} (2026.07)",
            "About Editor",
            parent=self,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    app = MarkEditor()
    app.mainloop()


if __name__ == "__main__":
    main()
