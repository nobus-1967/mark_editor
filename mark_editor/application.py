"""Gtk.Application subclass with actions and keyboard shortcuts."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, Gio, Gtk

from mark_editor.constants import CJK_CODES, EMOJIS, SPECIAL_SIGNS
from mark_editor.helpers import load_theme, resource_path


class MarkEditorApp(Gtk.Application):
    """Gtk.Application subclass that owns all actions, keyboard shortcuts and CSS."""

    def __init__(self) -> None:
        """Initialize the application with its ID and flags."""
        super().__init__(
            application_id="com.github.mark_editor",
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )
        self.connect("activate", self._on_activate)
        self.connect("startup", self._on_startup)

    def _on_startup(self, _app) -> None:
        """Load the CSS stylesheet, register actions and keyboard shortcuts."""
        css_provider = Gtk.CssProvider()
        css_path = resource_path("marks.css")
        try:
            css_provider.load_from_path(css_path)
        except Exception:
            pass
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        self._setup_actions()
        self._setup_shortcuts()

    def _on_activate(self, app) -> None:
        """Apply the saved theme and present the main window."""
        # Apply saved theme
        mode = load_theme()
        settings = Gtk.Settings.get_default()
        if mode == "dark":
            settings.set_property("gtk-application-prefer-dark-theme", True)
        else:
            settings.set_property("gtk-application-prefer-dark-theme", False)

        from mark_editor.window import MarkEditorWindow

        win = MarkEditorWindow(application=app)
        self._window = win
        win.present()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _add_action(self, name: str, callback) -> None:
        """Register a stateless ``Gio.SimpleAction`` on this application."""
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)

    def _setup_actions(self) -> None:
        """Create all application actions (file, edit, format, paragraph, view, help)."""

        def _w():
            """Return the current window instance."""
            return getattr(self, "_window", None)

        # File
        self._add_action("new", lambda a, p: _w() and _w()._on_new())
        self._add_action("open", lambda a, p: _w() and _w()._on_open())
        self._add_action("reopen", lambda a, p: _w() and _w()._on_reopen())
        self._add_action("save", lambda a, p: _w() and _w()._on_save())
        self._add_action("save-as", lambda a, p: _w() and _w()._on_save_as())
        self._add_action("convert", lambda a, p: _w() and _w()._on_convert())
        self._add_action("quit", lambda a, p: _w() and _w()._on_quit())

        # Edit
        self._add_action("undo", lambda a, p: _w() and _w()._on_undo())
        self._add_action("redo", lambda a, p: _w() and _w()._on_redo())
        self._add_action("cut", lambda a, p: _w() and _w()._on_cut())
        self._add_action("copy", lambda a, p: _w() and _w()._on_copy())
        self._add_action("paste", lambda a, p: _w() and _w()._on_paste())
        self._add_action("find", lambda a, p: _w() and _w()._on_find())
        self._add_action("replace", lambda a, p: _w() and _w()._on_replace())
        self._add_action("select-all", lambda a, p: _w() and _w()._on_select_all())
        self._add_action(
            "remove-selection", lambda a, p: _w() and _w()._on_remove_selection()
        )
        self._add_action("line-up", lambda a, p: _w() and _w()._on_line_up())
        self._add_action("line-down", lambda a, p: _w() and _w()._on_line_down())
        self._add_action("delete-line", lambda a, p: _w() and _w()._on_delete_line())

        # Format
        self._add_action("bold", lambda a, p: _w() and _w()._on_bold())
        self._add_action("italic", lambda a, p: _w() and _w()._on_italic())
        self._add_action("underline", lambda a, p: _w() and _w()._on_underline())
        self._add_action(
            "strikethrough", lambda a, p: _w() and _w()._on_strikethrough()
        )
        self._add_action("superscript", lambda a, p: _w() and _w()._on_superscript())
        self._add_action("subscript", lambda a, p: _w() and _w()._on_subscript())
        self._add_action("inline-code", lambda a, p: _w() and _w()._on_inline_code())
        self._add_action("mark", lambda a, p: _w() and _w()._on_mark())
        self._add_action("header-id", lambda a, p: _w() and _w()._on_header_id())
        self._add_action("header-link", lambda a, p: _w() and _w()._on_header_link())
        self._add_action("hyperlink", lambda a, p: _w() and _w()._on_hyperlink())
        self._add_action("footnote", lambda a, p: _w() and _w()._on_footnote())
        self._add_action(
            "language-marker", lambda a, p: _w() and _w()._on_language_marker()
        )
        self._add_action(
            "language-wrapping", lambda a, p: _w() and _w()._on_language_wrapping()
        )
        self._add_action("furigana", lambda a, p: _w() and _w()._on_furigana())
        self._add_action("date-time", lambda a, p: _w() and _w()._on_date_time())
        self._add_action("special-mark", lambda a, p: _w() and _w()._on_special_mark())
        self._add_action(
            "clear-formatting", lambda a, p: _w() and _w()._on_clear_formatting()
        )

        # Paragraph
        for level in range(1, 7):
            lv = level
            self._add_action(
                f"heading-{lv}", lambda a, p, l=lv: _w() and _w()._on_heading(l)
            )
        self._add_action("paragraph", lambda a, p: _w() and _w()._on_paragraph())
        self._add_action("ordered-list", lambda a, p: _w() and _w()._on_ordered_list())
        self._add_action(
            "unordered-list", lambda a, p: _w() and _w()._on_unordered_list()
        )
        self._add_action(
            "definition-list", lambda a, p: _w() and _w()._on_definition_list()
        )
        self._add_action("code-block", lambda a, p: _w() and _w()._on_code_block())
        self._add_action("blockquote", lambda a, p: _w() and _w()._on_blockquote())
        self._add_action("table", lambda a, p: _w() and _w()._on_table())
        self._add_action("image", lambda a, p: _w() and _w()._on_image())
        self._add_action("line-break", lambda a, p: _w() and _w()._on_line_break())
        self._add_action(
            "horizontal-rule", lambda a, p: _w() and _w()._on_horizontal_rule()
        )
        self._add_action("add-indent", lambda a, p: _w() and _w()._on_add_indent())
        self._add_action(
            "remove-indent", lambda a, p: _w() and _w()._on_remove_indent()
        )
        self._add_action("comment", lambda a, p: _w() and _w()._on_comment())
        self._add_action(
            "yaml-front-matter", lambda a, p: _w() and _w()._on_yaml_front_matter()
        )

        # View
        self._add_action("toggle-theme", lambda a, p: _w() and _w()._on_toggle_theme())
        self._add_action("editor-font", lambda a, p: _w() and _w()._on_editor_font())
        self._add_action("zoom-in", lambda a, p: _w() and _w()._on_zoom_in())
        self._add_action("zoom-out", lambda a, p: _w() and _w()._on_zoom_out())
        self._add_action("quick-view", lambda a, p: _w() and _w()._on_quick_view())
        self._add_action(
            "quick-view-css", lambda a, p: _w() and _w()._on_quick_view_css()
        )

        # Help
        self._add_action(
            "help-markdown-guide", lambda a, p: _w() and _w()._on_help_markdown_guide()
        )
        self._add_action("help-about", lambda a, p: _w() and _w()._on_help_about())

        # CJK Codes
        for code in CJK_CODES:
            c = code
            self._add_action(
                f"insert-cjk-{c}",
                lambda a, p, v=c: _w() and _w()._insert_text("{:" + v + ":}"),
            )

        # Emoji Shortcodes
        for emoji in EMOJIS:
            e = emoji
            self._add_action(
                f"insert-emoji-{e}",
                lambda a, p, v=f":{e}:": _w() and _w()._insert_text(v),
            )

        # Special Signs
        for name, sign in SPECIAL_SIGNS:
            safe_name = name.replace(" ", "-")
            s = sign
            self._add_action(
                f"insert-sign-{safe_name}",
                lambda a, p, v=s: _w() and _w()._insert_text(v),
            )

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def _setup_shortcuts(self) -> None:
        """Bind keyboard accelerators to all application actions."""
        shortcuts = [
            # File
            ("app.new", ["<Control>n"]),
            ("app.open", ["<Control>o"]),
            ("app.reopen", ["<Control><Shift>o"]),
            ("app.save", ["<Control>s"]),
            ("app.save-as", ["<Control><Shift>s"]),
            ("app.convert", ["<Control>e"]),
            ("app.quit", ["<Control>q"]),
            # Edit
            ("app.undo", ["<Control>z"]),
            ("app.redo", ["<Control><Shift>z"]),
            ("app.cut", ["<Control>x"]),
            ("app.copy", ["<Control>c"]),
            ("app.paste", ["<Control>v"]),
            ("app.find", ["<Control>f"]),
            ("app.replace", ["<Control>r"]),
            ("app.select-all", ["<Control>a"]),
            ("app.remove-selection", ["<Control><Shift>a"]),
            ("app.line-up", ["<Control>Up"]),
            ("app.line-down", ["<Control>Down"]),
            ("app.delete-line", ["<Control>y"]),
            # Format
            ("app.bold", ["<Control>b"]),
            ("app.italic", ["<Control>i"]),
            ("app.underline", ["<Control>u"]),
            ("app.strikethrough", ["<Control>d"]),
            ("app.superscript", ["<Control><Shift>p"]),
            ("app.subscript", ["<Control><Shift>b"]),
            ("app.inline-code", ["<Control>k"]),
            ("app.mark", ["<Control><Shift>m"]),
            ("app.header-id", ["<Control>h"]),
            ("app.header-link", ["<Control><Shift>h"]),
            ("app.hyperlink", ["<Control>l"]),
            ("app.footnote", ["<Control><Shift>u"]),
            ("app.language-marker", ["<Control>w"]),
            ("app.language-wrapping", ["<Control><Shift>w"]),
            ("app.furigana", ["<Control><Shift>j"]),
            ("app.date-time", ["<Control><Shift>d"]),
            ("app.special-mark", ["<Control><Shift>l"]),
            ("app.clear-formatting", ["<Control><Shift>f"]),
            # Paragraph
            ("app.heading-1", ["<Alt><Control>1"]),
            ("app.heading-2", ["<Alt><Control>2"]),
            ("app.heading-3", ["<Alt><Control>3"]),
            ("app.heading-4", ["<Alt><Control>4"]),
            ("app.heading-5", ["<Alt><Control>5"]),
            ("app.heading-6", ["<Alt><Control>6"]),
            ("app.paragraph", ["<Alt><Control>0"]),
            ("app.ordered-list", ["<Control>g"]),
            ("app.unordered-list", ["<Control><Shift>g"]),
            ("app.definition-list", ["<Control><Shift>x"]),
            ("app.code-block", ["<Control><Shift>k"]),
            ("app.blockquote", ["<Control><Shift>q"]),
            ("app.table", ["<Control>t"]),
            ("app.image", ["<Control><Shift>i"]),
            ("app.line-break", ["<Control>backslash"]),
            ("app.horizontal-rule", ["<Control>underscore"]),
            ("app.comment", ["<Control>m"]),
            ("app.yaml-front-matter", ["<Control><Shift>y"]),
            ("app.add-indent", ["Tab"]),
            ("app.remove-indent", ["<Shift>Tab"]),
            # View
            ("app.toggle-theme", ["<Control><Shift>t"]),
            ("app.editor-font", ["<Control><Alt>f"]),
            ("app.zoom-in", ["<Control>equal", "<Control>plus"]),
            ("app.zoom-out", ["<Control>minus"]),
            ("app.quick-view", ["<Control><Alt>v"]),
            ("app.quick-view-css", ["<Control><Alt>c"]),
        ]

        for action_name, accels in shortcuts:
            try:
                self.set_accels_for_action(action_name, accels)
            except Exception:
                pass
