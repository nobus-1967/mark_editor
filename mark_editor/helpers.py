"""Helper utilities: resources, themes, caching, temp files, markdown conversion."""

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


def md_to_plain(text: str) -> str:
    """Strip Markdown syntax to produce plain text.

    Removes block syntax (code fences, heading/list markers, horizontal
    rules, ``::`` markers, empty pipe rows), normalizes table alignment rows
    (``:--``/``--:``/``:--:`` ``->`` ``--``) and preserves ``| === |`` footer
    separators, strips known curly-brace extension markers only, removes
    inline emphasis, and collapses blank lines.
    """
    text = re.sub(r"^```[^\n]*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^#+\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*([-*+>])\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*(\|\s*)+$", "", text, flags=re.MULTILINE)
    footer_rows: list[str] = []

    def _mask_footer(m: re.Match) -> str:
        """Hide a ``| === |`` footer separator so ``=`` stripping skips it."""
        footer_rows.append(m.group(0))
        return f"\x00{len(footer_rows) - 1}\x00"

    text = re.sub(
        r"^\s*\|\s*([ \t]*=+[ \t]*\|)+$", _mask_footer, text, flags=re.MULTILINE
    )
    text = re.sub(
        r"^\s*\|\s*([ \t]*:?-{3,}:?[ \t]*\|)+$",
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
    text = re.sub(r"\{[^|}]+\|[^}]*\}", "", text)  # ruby/furigana: {text|reading}
    text = re.sub(r"[*_~^`=]{1,2}", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    for i, row in enumerate(footer_rows):
        text = text.replace(f"\x00{i}\x00", row)
    return text.strip() + "\n"
