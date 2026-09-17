"""Helper utilities for Mark Editor.

Resources, themes, caching, temp files, markdown conversion and the table of
contents generator.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from markdown2html5_base import MarkdownToHTML
from markdown2pdf_base import convert as md2pdf_convert

from mark_editor.constants import (
    CACHE_DIR,
    CONFIG_DIR,
    DEFAULT_THEME,
    TEMP_MD,
    THEME_FILE,
    THEMES,
)

# ---------------------------------------------------------------------------
# Resource paths
# ---------------------------------------------------------------------------


def resource_path(relative: str) -> str:
    """Return an absolute path for a bundled resource (PyInstaller aware)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


# ---------------------------------------------------------------------------
# Theme persistence
# ---------------------------------------------------------------------------


def _read_config() -> dict:
    """Read ~/.config/mark_editor/theme.json as a dict (empty on any error)."""
    try:
        return json.loads(THEME_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_config(**updates) -> None:
    """Merge *updates* into theme.json, preserving existing keys (best effort)."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = _read_config()
        data.update(updates)
        THEME_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_theme() -> str:
    """Load the saved appearance mode from ~/.config/mark_editor/theme.json."""
    name = str(_read_config().get("mode", DEFAULT_THEME)).lower()
    return name if name in THEMES else DEFAULT_THEME


def load_font() -> tuple[str, int]:
    """Load saved editor font family and size from theme.json.

    Returns ``(family, size)`` or the defaults ``("Noto Sans Mono", 16)``.
    """
    data = _read_config()
    family = data.get("font_family", "Noto Sans Mono")
    size = int(data.get("font_size", 16))
    return family, size


def save_theme(name: str) -> None:
    """Save the current appearance mode."""
    _write_config(mode=name)


def save_font(family: str, size: int) -> None:
    """Save the editor font family and size to theme.json (preserving mode)."""
    _write_config(font_family=family, font_size=size)


# ---------------------------------------------------------------------------
# Cache directory
# ---------------------------------------------------------------------------


def ensure_cache_dir() -> Path:
    """Create and return ~/.cache/mark_editor."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


# ---------------------------------------------------------------------------
# Temp file management
# ---------------------------------------------------------------------------


def get_temp_md_path(current_file: Path | None) -> Path:
    """Return the temp Markdown file path based on current_file.

    - No file saved yet: ~/.cache/mark_editor/Temp.md
    - File saved/opened: <dir>/~<name>.md
    """
    if current_file is None:
        return ensure_cache_dir() / TEMP_MD
    return current_file.parent / f"~{current_file.name}"


def get_temp_html_path(current_file: Path | None) -> Path:
    """Return the temp HTML file path for quick viewing.

    - No file saved yet: ~/.cache/mark_editor/Temp.html
    - File saved/opened: <dir>/~<stem>.html
    """
    if current_file is None:
        return ensure_cache_dir() / "Temp.html"
    stem = current_file.stem
    return current_file.parent / f"~{stem}.html"


def save_temp_md(text: str, current_file: Path | None) -> None:
    """Save text to the temp Markdown file."""
    path = get_temp_md_path(current_file)
    path.write_text(text, encoding="utf-8")


def load_temp_md(current_file: Path | None) -> str | None:
    """Load text from the temp Markdown file. Returns None if not found."""
    path = get_temp_md_path(current_file)
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    return None


def save_temp_html(html: str, current_file: Path | None) -> Path:
    """Save HTML content to temp file and return the path."""
    path = get_temp_html_path(current_file)
    path.write_text(html, encoding="utf-8")
    return path


def _delete_tilde_files(directory: Path, suffix: str) -> None:
    """Delete ``~*<suffix>`` files in the given directory (best effort)."""
    try:
        if directory.exists():
            for f in directory.iterdir():
                if f.is_file() and f.name.startswith("~") and f.name.endswith(suffix):
                    f.unlink()
    except Exception:
        pass


def cleanup_temp_md(directory: Path) -> None:
    """Delete temporary Markdown files (~*.md) in the given directory."""
    _delete_tilde_files(directory, ".md")


def cleanup_temp_html(directory: Path) -> None:
    """Delete temporary HTML files (~*.html) in the given directory."""
    _delete_tilde_files(directory, ".html")


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------

_converter: MarkdownToHTML | None = None


def get_converter() -> MarkdownToHTML:
    """Return the singleton MarkdownToHTML converter (lazy initialisation)."""
    global _converter
    if _converter is None:
        _converter = MarkdownToHTML()
    return _converter


def md_to_html(text: str, *, include_css: bool = False) -> str:
    """Convert Markdown *text* to HTML5 using markdown2html5-base."""
    return get_converter().convert(text, include_css=include_css)


def md_to_pdf(text: str, path: str, *, source_dir: str | None = None) -> None:
    """Convert Markdown *text* to PDF and save to *path* via pandoc/xelatex.

    ``source_dir`` is the directory used to resolve relative image paths;
    it falls back to the output file's own directory when omitted.
    """
    if source_dir is None:
        source_dir = os.path.dirname(os.path.abspath(path))
    md2pdf_convert(text, path, source_dir=source_dir)


_DEF_RE = re.compile(r"^\s*:\s+\S")

_LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+\S")


def _separate_lists(text: str) -> str:
    """Insert a blank line before ordered, unordered, todo and definition lists."""
    out: list[str] = []
    last: int | None = None
    in_list = False
    for line in text.split("\n"):
        if not line.strip():
            in_list = False
            out.append(line)
            continue
        if _LIST_RE.match(line):
            if not in_list and last is not None and out[last].strip():
                out.append("")
            in_list = True
            out.append(line)
            last = len(out) - 1
            continue
        if _DEF_RE.match(line):
            if (
                last is not None
                and out[last].strip()
                and not _LIST_RE.match(out[last])
                and not _DEF_RE.match(out[last])
                and not out[last].strip().startswith("```")
                and (last == 0 or out[last - 1].strip())
            ):
                out.insert(last, "")
                last += 1
            in_list = True
            out.append(line)
            last = len(out) - 1
            continue
        in_list = False
        out.append(line)
        last = len(out) - 1
    return "\n".join(out)


def _strip_blockquotes(text: str) -> str:
    """Remove ``>`` blockquote markers, keeping a blank line before each block."""
    out: list[str] = []
    in_quote = False
    for line in text.split("\n"):
        m = re.match(r"^[ \t]*>+[ \t]?", line)
        if m is not None:
            if not in_quote and out and out[-1].strip():
                out.append("")
            in_quote = True
            out.append(line[m.end() :])
        else:
            in_quote = False
            out.append(line)
    return "\n".join(out)


_FOOTNOTE_RE = re.compile(r"^\[\^?[^\]]+\]:\s")


def _compact_footnotes(text: str) -> str:
    """Drop blank lines that sit between consecutive footnote definitions."""
    lines = text.split("\n")
    out: list[str] = []
    prev = ""
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            j = i
            while j < n and not lines[j].strip():
                j += 1
            between = (
                _FOOTNOTE_RE.match(prev) and j < n and _FOOTNOTE_RE.match(lines[j])
            )
            if between:
                i = j
                continue
        out.append(line)
        if line.strip():
            prev = line
        i += 1
    return "\n".join(out)


def _separate_code_blocks(text: str) -> str:
    """Insert a blank line after each fenced code block that has content next."""
    out: list[str] = []
    in_fence = False
    just_closed = False
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            out.append(line)
            in_fence = not in_fence
            just_closed = not in_fence
            continue
        if just_closed and line.strip():
            out.append("")
        just_closed = False
        out.append(line)
    return "\n".join(out)


def md_to_plain(text: str) -> str:
    """Strip Markdown syntax to produce plain text.

    Removes block syntax (code fences, heading markers, horizontal rules,
    ``::`` markers, empty pipe rows), normalizes table alignment rows
    (``:---:`` / ``:---`` / ``---:`` to ``---``) and preserves ``| === |``
    footer separators and the ordered/unordered/todo/definition list markers
    (``1. ``/``- ``/``* ``, with definition ``: `` converted to ``- ``), keeps
    a blank line before blockquotes and lists (ordered, unordered, todo and
    definition lists) and after fenced code blocks, keeps footnote definitions
    adjacent (no blank line after them), strips known curly-brace extension
    markers only, removes inline emphasis, and collapses blank lines.
    """
    text = _separate_code_blocks(text)
    text = re.sub(r"^```[^\n]*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^#+\s?", "", text, flags=re.MULTILINE)
    text = _separate_lists(text)
    text = _strip_blockquotes(text)
    text = re.sub(r"^:[ \t]+", "- ", text, flags=re.MULTILINE)
    text = re.sub(r"^[ \t]*(\|[ \t]*)+$", "", text, flags=re.MULTILINE)
    footer_rows: list[str] = []

    def _mask_footer(m: re.Match) -> str:
        """Hide a ``| === |`` footer separator so ``=`` stripping skips it."""
        footer_rows.append(m.group(0))
        return f"\x00{len(footer_rows) - 1}\x00"

    text = re.sub(
        r"^[ \t]*\|[ \t]*([ \t]*=+[ \t]*\|)+$", _mask_footer, text, flags=re.MULTILINE
    )
    text = re.sub(
        r"^[ \t]*\|[ \t]*([ \t]*:?-{3,}:?[ \t]*\|)+$",
        lambda m: re.sub(r":?-{3,}:?", "---", m.group(0)),
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(r"^---\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^:::+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\[.*?\]:\s*#\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # Strip known Markdown extension curly-brace patterns only
    text = re.sub(r"\{#[^}]*\}", "", text)  # header IDs: {#id}
    text = re.sub(r"\{:[^}]*\}", "", text)  # language markers: {:lang}
    text = re.sub(r"\{([^|}]+)\|([^}]*)\}", r"\1(\2)", text)  # furigana
    text = re.sub(r"[*_~^`=]{1,2}", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = _compact_footnotes(text)
    for i, row in enumerate(footer_rows):
        text = text.replace(f"\x00{i}\x00", row)
    return text.strip() + "\n"


# ---------------------------------------------------------------------------
# Table of contents
# ---------------------------------------------------------------------------


TOC_BEGIN_MARKER = "[TOC: Begin]: #"
TOC_END_MARKER = "[TOC: End]: #"
TOC_HEADING_LABEL = "Table of Contents"

_TOC_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_TOC_ID_RE = re.compile(r"\s*\{#[^{}]*\}\s*$")
_TOC_ID_TEXT_RE = re.compile(r"\{#([^{}]*)\}\s*$")
_AUTO_ID_RE = re.compile(r"h\d+-\d+")


def _find_toc_block(lines: list[str], fold_lead: bool = True) -> tuple[int, int] | None:
    """Return the ``[begin, end]`` line indices of the TOC block in *lines*.

    The block spans from the ``[TOC: Begin]: #`` marker to the ``[TOC: End]: #``
    marker plus its separating ``***`` rule and one following blank line. When
    *fold_lead* is set, one adjacent blank line before the marker is included
    too. Returns None when no marker pair is found.
    """
    begin = next(
        (i for i, ln in enumerate(lines) if ln.rstrip() == TOC_BEGIN_MARKER), None
    )
    if begin is None:
        return None
    if fold_lead and begin > 0 and not lines[begin - 1].strip():
        begin -= 1
    end = next(
        (
            i
            for i in range(begin + 1, len(lines))
            if lines[i].rstrip() == TOC_END_MARKER
        ),
        None,
    )
    if end is None:
        return None
    j = end + 1
    if j < len(lines) and not lines[j].strip():
        j += 1
    if j < len(lines) and lines[j].strip() == "***":
        end = j
        j += 1
        if j < len(lines) and not lines[j].strip():
            end = j
    return begin, end


def _process_headings(
    lines: list[str],
    refresh_auto: bool,
    skip: tuple[int, int] | None = None,
) -> tuple[list[tuple[int, str, str]], int | None]:
    """Assign heading IDs in-place and return TOC entries and the H1 anchor.

    Skips headings between *skip* (a ``(begin, end)`` line range, e.g. an
    existing TOC block). Level 1 headings get no ID and are not listed; the
    returned anchor is the line *after* the first Level 1 heading. Existing IDs
    are kept (and reused in TOC links); auto IDs ``#hX-Y`` are renumbered when
    *refresh_auto* is True.
    """
    counters: dict[int, int] = {}
    entries: list[tuple[int, str, str]] = []
    insert_idx: int | None = None
    in_fence = False
    for i, line in enumerate(lines):
        if skip is not None and skip[0] <= i <= skip[1]:
            continue
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _TOC_HEADING_RE.match(line)
        if not m:
            continue
        level = len(m.group(1))
        if insert_idx is None and level == 1:
            insert_idx = i + 1
        if level < 2:
            continue
        counters[level] = counters.get(level, 0) + 1
        title = _TOC_ID_RE.sub("", m.group(2)).strip()
        existing = _TOC_ID_TEXT_RE.search(line)
        if existing is not None:
            hid = existing.group(1).strip() or f"h{level}"
            if refresh_auto and _AUTO_ID_RE.fullmatch(hid):
                hid = f"h{level}-{counters[level]}"
                lines[i] = _TOC_ID_RE.sub("", line) + f" {{#{hid}}}"
        else:
            hid = f"h{level}-{counters[level]}"
            lines[i] = line.rstrip() + f" {{#{hid}}}"
        entries.append((level, title, hid))
    return entries, insert_idx


def _toc_block_text(
    entries: list[tuple[int, str, str]], heading: str = TOC_HEADING_LABEL
) -> str:
    """Build the marked TOC block text (title, links, separator) for *entries*."""
    lines = [TOC_BEGIN_MARKER, "", f"## {heading} {{#toc}}", ""]
    for _, title, hid in entries:
        lines.append(f"- [{title}](#{hid})")
    lines.extend(["", TOC_END_MARKER, "", "***"])
    return "\n".join(lines)


def _insert_toc(
    lines: list[str],
    entries,
    anchor: int | None,
    heading: str | None = None,
) -> list[str]:
    """Insert the TOC block into *lines* after *anchor*, front matter or start.

    The block owns its blank padding (one line before the marker and one line
    after the ``***`` rule), so inserts and replacements are spacing-stable.
    """
    if not entries:
        return lines
    if anchor is None:
        if lines and lines[0].strip() == "---":
            closing = next(
                (i for i in range(1, len(lines)) if lines[i].strip() == "---"), None
            )
            anchor = closing + 1 if closing is not None else len(lines)
        else:
            anchor = 0
    block = _toc_block_text(entries, heading or TOC_HEADING_LABEL).split("\n")
    if anchor == 0:
        block.append("")
        lines[anchor:anchor] = block
        return lines
    block = [""] + block + [""]
    if anchor < len(lines) and not lines[anchor].strip():
        lines[anchor : anchor + 1] = block
    else:
        lines[anchor:anchor] = block
    return lines


def remove_toc(text: str) -> str:
    """Return *text* without the auto-generated table of contents block.

    Heading IDs are left untouched.
    """
    lines = text.split("\n")
    block = _find_toc_block(lines, fold_lead=False)
    if block is None:
        return text
    begin, end = block
    del lines[begin : end + 1]
    return "\n".join(lines)


def add_toc(text: str, heading: str | None = None) -> str:
    """Return *text* with a table of contents inserted after an existing one is removed.

    Level-2+ headings are assigned ``{#hX-Y}`` IDs (only when missing), and a
    ``## <heading> {#toc}`` block with ``- [Text](#hX-Y)`` links is inserted
    after the first Level 1 heading, else at the document start after any YAML
    front matter. *heading* defaults to ``Table of Contents``. The block is
    separated from the following text by ``***``.
    """
    lines = text.split("\n")
    block = _find_toc_block(lines)
    if block is not None:
        del lines[block[0] : block[1] + 1]
    entries, anchor = _process_headings(lines, refresh_auto=False)
    return "\n".join(_insert_toc(lines, entries, anchor, heading))


def regenerate_toc(text: str, heading: str | None = None) -> str:
    """Return *text* with the TOC rebuilt and auto ``#hX-Y`` headings renumbered.

    *heading* sets the ``## <heading> {#toc}`` title, defaulting to
    ``Table of Contents``.
    """
    lines = text.split("\n")
    block = _find_toc_block(lines)
    if block is not None:
        del lines[block[0] : block[1] + 1]
    entries, anchor = _process_headings(lines, refresh_auto=True)
    return "\n".join(_insert_toc(lines, entries, anchor, heading))


def add_heading_ids(text: str) -> str:
    """Return *text* with ``{#hX-Y}`` IDs added to level-2+ headings that lack one.

    The TOC block (if present) and Level 1 headings are left untouched.
    """
    lines = text.split("\n")
    skip = _find_toc_block(lines)
    _process_headings(lines, refresh_auto=False, skip=skip)
    return "\n".join(lines)
