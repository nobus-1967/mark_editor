"""Application constants."""

from __future__ import annotations

from pathlib import Path

APP_NAME = "Mark Editor"
VERSION = "0.6.3"
RELEASE = "2026.09"

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
    ("up arrow", "&uarr;"),
    ("down arrow", "&darr;"),
    ("logical implication", "=>"),
    ("slash", "&#47;"),
    ("backslash", "&#92;"),
    ("left angle quote", "<<"),
    ("left double quote", "&ldquo;"),
    ("right angle quote", ">>"),
    ("right double quote", "&rdquo;"),
    ("em dash", "---"),
    ("en dash", "--"),
    ("ellipsis", "..."),
    ("non-breaking space", "&nbsp;"),
]

LANGUAGE_TAGS: tuple[str, ...] = (
    "de",
    "de-AT",
    "de-DE",
    "en",
    "en-GB",
    "en-US",
    "es",
    "fr",
    "ja",
    "it",
    "ko",
    "ko-KR",
    "pt",
    "pt-BR",
    "pt-PT",
    "ru",
    "uk",
    "zh",
    "zh-Hans-CN",
    "zh-Hant",
    "zh-Hant-HK",
    "zh-Hant-TW",
)

LANGUAGE_CODES: tuple[tuple[str, str], ...] = (
    ("de", "German (Generic)"),
    ("de-AT", "German (Austria)"),
    ("de-DE", "German (Germany)"),
    ("en", "English (Generic)"),
    ("en-GB", "British English (United Kingdom)"),
    ("en-US", "American English (United States)"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("it", "Italian"),
    ("ja", "Japanese"),
    ("ru", "Russian"),
    ("uk", "Ukrainian"),
    ("ko", "Korean (Generic)"),
    ("ko-KR", "Korean (South Korea)"),
    ("pt", "Portuguese (Generic)"),
    ("pt-BR", "Brazilian Portuguese (Brazil)"),
    ("pt-PT", "European Portuguese (Portugal)"),
    ("zh", "Chinese (Generic)"),
    ("zh-Hans-CN", "Simplified Chinese (Mainland China)"),
    ("zh-Hant", "Traditional Chinese (Generic)"),
    ("zh-Hant-HK", "Traditional Chinese (Hong Kong)"),
    ("zh-Hant-TW", "Traditional Chinese (Taiwan)"),
)

EDITOR_FONT_SIZE = 16
ZOOM_STEP = 2
