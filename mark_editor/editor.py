"""GtkSourceView-based Markdown editor widget."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GtkSource", "5")

from gi.repository import Gdk, Gtk, GtkSource

from mark_editor.constants import EDITOR_COLORS


class Editor(Gtk.Box):
    """A SourceView editor with built-in line numbers and search highlighting."""

    def __init__(self, mode: str = "light") -> None:
        """Initialize the editor with the given theme *mode*."""
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_vexpand(True)
        self.set_hexpand(True)

        self._mode = mode

        # --- Buffer ---
        self._buffer = GtkSource.Buffer()
        self._buffer.set_highlight_matching_brackets(False)
        self._buffer.set_enable_undo(True)

        # --- View ---
        self._view = GtkSource.View.new_with_buffer(self._buffer)
        self._view.set_show_line_numbers(True)
        self._view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._view.set_left_margin(8)
        self._view.set_right_margin(8)
        self._view.set_top_margin(8)
        self._view.set_bottom_margin(8)
        self._view.set_monospace(True)
        self._view.set_tab_width(4)
        self._view.set_insert_spaces_instead_of_tabs(True)
        self._view.set_highlight_current_line(True)
        self._view.add_css_class("mark-editor")

        # --- Search context (highlights all matches) ---
        self._search_settings = GtkSource.SearchSettings()
        self._search_context = GtkSource.SearchContext.new(
            self._buffer, self._search_settings
        )
        self._search_context.set_highlight(True)

        # --- Scrolled window ---
        self._scroll = Gtk.ScrolledWindow()
        self._scroll.set_child(self._view)
        self._scroll.set_vexpand(True)
        self._scroll.set_hexpand(True)
        self._scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._scroll.set_kinetic_scrolling(True)
        self.append(self._scroll)

        self._apply_colors(mode)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_buffer(self) -> GtkSource.Buffer:
        """Return the underlying GtkSource.Buffer."""
        return self._buffer

    def get_view(self) -> GtkSource.View:
        """Return the underlying GtkSource.View widget."""
        return self._view

    def get_text(self) -> str:
        """Return the full buffer content as a string."""
        start = self._buffer.get_start_iter()
        end = self._buffer.get_end_iter()
        return self._buffer.get_text(start, end, include_hidden_chars=False)

    def set_text(self, text: str) -> None:
        """Replace the entire buffer content with *text*."""
        self._buffer.set_text(text)
        self._buffer.set_modified(False)

    def insert_at_cursor(self, text: str) -> None:
        """Insert *text* at the current cursor position."""
        self._buffer.begin_user_action()
        self._buffer.insert_at_cursor(text, -1)
        self._buffer.end_user_action()

    def insert_at_iter(self, iter_: Gtk.TextIter, text: str) -> None:
        """Insert *text* at the given text iterator position."""
        self._buffer.begin_user_action()
        self._buffer.insert(iter_, text, -1)
        self._buffer.end_user_action()

    def delete_selection(self) -> None:
        """Delete the currently selected text."""
        if self._buffer.get_has_selection():
            start, end = self._buffer.get_selection_bounds()
            self._buffer.begin_user_action()
            self._buffer.delete(start, end)
            self._buffer.end_user_action()

    def select_all(self) -> None:
        """Select the entire document."""
        start = self._buffer.get_start_iter()
        end = self._buffer.get_end_iter()
        self._buffer.select_range(start, end)

    def get_selection_bounds(self) -> tuple[Gtk.TextIter, Gtk.TextIter] | None:
        """Return (start, end) iterators of the selection, or None."""
        if self._buffer.get_has_selection():
            return self._buffer.get_selection_bounds()
        return None

    def get_selected_text(self) -> str:
        """Return the currently selected text, or an empty string."""
        bounds = self.get_selection_bounds()
        if bounds is None:
            return ""
        start, end = bounds
        return self._buffer.get_text(start, end, include_hidden_chars=False)

    def replace_selection(self, text: str) -> None:
        """Replace the current selection with *text*, or insert at cursor."""
        self._buffer.begin_user_action()
        if self._buffer.get_has_selection():
            start, end = self._buffer.get_selection_bounds()
            self._buffer.delete(start, end)
            self._buffer.insert(start, text, -1)
        else:
            self._buffer.insert_at_cursor(text, -1)
        self._buffer.end_user_action()

    def wrap_selection(self, wrapper: str) -> None:
        """Surround the selection with *wrapper* characters, or place a pair at cursor."""
        bounds = self.get_selection_bounds()
        self._buffer.begin_user_action()
        if bounds is not None:
            start, end = bounds
            selected = self._buffer.get_text(start, end, include_hidden_chars=False)
            self._buffer.delete(start, end)
            replacement = f"{wrapper}{selected}{wrapper}"
            self._buffer.insert(start, replacement, -1)
            new_end = start.copy()
            new_end.forward_chars(len(replacement))
            self._buffer.select_range(start, new_end)
        else:
            self._buffer.insert_at_cursor(f"{wrapper}{wrapper}", -1)
            cursor = self._buffer.get_iter_at_mark(self._buffer.get_insert())
            cursor.backward_chars(len(wrapper))
            self._buffer.place_cursor(cursor)
        self._buffer.end_user_action()

    def undo(self) -> bool:
        """Undo the last editing action."""
        return self._buffer.undo()

    def redo(self) -> bool:
        """Redo the last undone editing action."""
        return self._buffer.redo()

    def can_undo(self) -> bool:
        """Return True if an undo operation is available."""
        return self._buffer.can_undo()

    def can_redo(self) -> bool:
        """Return True if a redo operation is available."""
        return self._buffer.can_redo()

    def get_current_line_number(self) -> int:
        """Return the 1-based line number of the cursor."""
        mark = self._buffer.get_insert()
        iter_ = self._buffer.get_iter_at_mark(mark)
        return iter_.get_line() + 1

    def get_line_count(self) -> int:
        """Return the total number of lines in the buffer."""
        return self._buffer.get_line_count()

    def get_line_text(self, line_number: int) -> str:
        """Return the text of the 1-based *line_number* (without trailing newline)."""
        _, iter_ = self._buffer.get_iter_at_line(line_number - 1)
        end = iter_.copy()
        if not end.ends_line():
            end.forward_to_line_end()
        return self._buffer.get_text(iter_, end, include_hidden_chars=False)

    def replace_line(self, line_number: int, new_text: str) -> None:
        """Replace the content of the 1-based *line_number* with *new_text*."""
        _, start = self._buffer.get_iter_at_line(line_number - 1)
        end = start.copy()
        if not end.ends_line():
            end.forward_to_line_end()
        self._buffer.begin_user_action()
        self._buffer.delete(start, end)
        self._buffer.insert(start, new_text, -1)
        self._buffer.end_user_action()

    def get_cursor_iter(self) -> Gtk.TextIter:
        """Return a TextIter at the current cursor position."""
        return self._buffer.get_iter_at_mark(self._buffer.get_insert())

    def set_cursor_iter(self, iter_: Gtk.TextIter) -> None:
        """Move the cursor to the position given by *iter_*."""
        self._buffer.place_cursor(iter_)

    def scroll_to_cursor(self) -> None:
        """Scroll the view so the cursor is visible on screen."""
        mark = self._buffer.get_insert()
        self._view.scroll_mark_onscreen(mark, True)

    def clear(self) -> None:
        """Clear the entire buffer content."""
        self._buffer.begin_user_action()
        self._buffer.set_text("")
        self._buffer.end_user_action()
        self._buffer.set_modified(False)

    def set_modified(self, modified: bool) -> None:
        """Mark the buffer as modified or unmodified."""
        self._buffer.set_modified(modified)

    def is_modified(self) -> bool:
        """Return True if the buffer has been modified since last save."""
        return self._buffer.get_modified()

    def connect_modified(self, callback) -> int:
        """Connect *callback* to the buffer's modified-changed signal."""
        return self._buffer.connect("modified-changed", callback)

    def connect_changed(self, callback) -> int:
        """Connect *callback* to the buffer's changed signal."""
        return self._buffer.connect("changed", callback)

    def set_font_size(self, size: int) -> None:
        """Set the editor font size in pixels via CSS."""
        css = f".mark-editor {{ font-size: {size}px; }}"
        provider = Gtk.CssProvider()
        provider.load_from_string(css)
        self._view.get_style_context().add_provider(
            provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def set_font_family(self, family: str) -> None:
        """Set the editor font family via CSS."""
        css = f".mark-editor {{ font-family: {family}, monospace; }}"
        provider = Gtk.CssProvider()
        provider.load_from_string(css)
        self._view.get_style_context().add_provider(
            provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def focus(self) -> None:
        """Transfer keyboard focus to the editor view."""
        self._view.grab_focus()

    def replace_all(
        self, find_text: str, replace_text: str, use_regex: bool = False
    ) -> int:
        """Replace every occurrence of *find_text* with *replace_text*.

        When *use_regex* is True the search string is treated as a regular
        expression.  Returns the number of replacements made.
        """
        import re as _re

        content = self.get_text()
        if use_regex:
            pattern = _re.compile(find_text)
            new_content, count = _re.subn(pattern, replace_text, content)
        else:
            new_content = content.replace(find_text, replace_text)
            count = content.count(find_text)
        if count > 0:
            self._buffer.set_text(new_content)
        return count

    # --- Search highlighting ---

    def set_search_pattern(self, pattern: str, case_sensitive: bool = False) -> None:
        """Highlight all occurrences of *pattern* in the buffer."""
        if not pattern:
            self._search_settings.set_search_text(None)
        else:
            self._search_settings.set_search_text(pattern)
            self._search_settings.set_case_sensitive(case_sensitive)

    def clear_search(self) -> None:
        """Remove all search highlights from the buffer."""
        self._search_settings.set_search_text(None)

    # --- Theme ---

    def set_mode(self, mode: str) -> None:
        """Switch the editor color scheme ('light' or 'dark')."""
        self._mode = mode
        self._apply_colors(mode)

    def _apply_colors(self, mode: str) -> None:
        """Apply foreground and background colors for the given *mode*."""
        colors = EDITOR_COLORS.get(mode, EDITOR_COLORS["light"])
        css = f"""
        .mark-editor sourceview {{
            background: {colors['bg']};
            color: {colors['fg']};
        }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_string(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
