"""Application constants."""

from __future__ import annotations

from pathlib import Path

APP_NAME = "Mark Editor"
<<<<<<< HEAD
VERSION = "0.6.2"
=======
VERSION = "0.6.0"
>>>>>>> parent of 6337a92 (Enhance Release (0.6.1))
RELEASE = "2026.08"

CONFIG_DIR = Path.home() / ".config" / "mark_editor"
THEME_FILE = CONFIG_DIR / "theme.json"

CACHE_DIR = Path.home() / ".cache" / "mark_editor"
TEMP_MD = "Temp.md"

THEMES: tuple[str, ...] = ("light", "dark")
DEFAULT_THEME = "light"

EDITOR_COLORS: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#ffffff",
        "fg": "#0f172a",
        "cursor": "#0f172a",
        "find_bg": "#fff3cd",
        "find_fg": "#1f2937",
        "border": "#cbd5e1",
    },
    "dark": {
        "bg": "#14181f",
        "fg": "#dee7f5",
        "cursor": "#dee7f5",
        "find_bg": "#2f4a78",
        "find_fg": "#f2f6ff",
        "border": "#2e3746",
    },
}

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

CJK_CODES: tuple[str, ...] = (
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
)

EDITOR_FONT_SIZE = 16
ZOOM_STEP = 2
