"""Main application window (GTK4)."""

from __future__ import annotations

import re
import webbrowser
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GtkSource", "5")

from gi.repository import Gdk, Gio, GLib, Gtk, GtkSource, Pango

from mark_editor.constants import (
    APP_NAME,
    EMOJIS,
    LANGUAGE_TAGS,
    SPECIAL_SIGNS,
    THEMES,
    VERSION,
)
from mark_editor.dialogs import (
    AboutDialog,
    ChoiceDialog,
    DateTimeDialog,
    DefinitionListDialog,
    FindDialog,
    FootnoteDialog,
    FuriganaDialog,
    HeaderLinkDialog,
    ReplaceDialog,
    TableDialog,
    YAMLFrontMatterDialog,
    ask_string,
    show_message,
)
from mark_editor.editor import Editor
from mark_editor.helpers import (
    cleanup_tilde_files,
    ensure_cache_dir,
    load_temp_md,
    load_theme,
    load_font,
    md_to_html,
    md_to_pdf,
    md_to_plain,
    save_temp_html,
    save_temp_md,
    save_theme,
    save_font,
)


class MarkEditorWindow(Gtk.ApplicationWindow):
    """The main Mark Editor application window."""

    def __init__(self, **kwargs) -> None:
        """Initialize the main editor window with saved settings."""
        super().__init__(**kwargs)
        self.set_title(APP_NAME)
        self.set_default_size(1100, 700)
        self.set_size_request(600, 400)

        self._theme_mode = load_theme()
        self._editor_font_family, self.editor_font_size = load_font()
        self.current_file: Path | None = None
        self.is_modified = False
        self._idle_update_pending = False

        self._build_ui()
        self._restore_pending_text()
        self._update_title()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Assemble the main window layout: header bar, menu, editor, status bar."""
        # ── Header bar (set_titlebar) ──
        header = Gtk.HeaderBar()
        menu_model = self._build_menu_model()
        menu_btn = Gtk.MenuButton()
        menu_btn.set_menu_model(menu_model)
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_tooltip_text("Menu")
        header.pack_end(menu_btn)
        self.set_titlebar(header)

        # ── Main vertical box ──
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.set_vexpand(True)
        vbox.set_hexpand(True)

        # ── Menu bar ──
        menubar_model = self._build_menubar_model()
        self._menubar = Gtk.PopoverMenuBar.new_from_model(menubar_model)
        self._menubar.set_hexpand(True)
        vbox.append(self._menubar)

        # ── Editor ──
        self._editor = Editor(mode=self._theme_mode)
        self._editor.set_vexpand(True)
        self._editor.set_hexpand(True)
        vbox.append(self._editor)

        # ── Status bar ──
        self._status_label = Gtk.Label(label="Ln 1, Col 1")
        self._status_label.set_xalign(1.0)
        self._status_label.set_margin_start(12)
        self._status_label.set_margin_end(12)
        self._status_label.set_margin_top(4)
        self._status_label.set_margin_bottom(4)
        self._status_label.add_css_class("status-bar")
        vbox.append(self._status_label)

        self.set_child(vbox)

        # Apply saved font settings
        self._editor.set_font_family(self._editor_font_family)
        self._editor.set_font_size(self.editor_font_size)

        # Apply dark class to status bar if saved theme is dark
        if self._theme_mode == "dark":
            self._status_label.add_css_class("dark")

        # Connect editor signals
        buf = self._editor.get_buffer()
        buf.connect("modified-changed", self._on_editor_modified)
        buf.connect("changed", self._on_editor_changed)

    # ------------------------------------------------------------------
    # Menu models (GMenu)
    # ------------------------------------------------------------------

    def _build_menubar_model(self) -> Gio.Menu:
        """Return the full menu-bar model (File / Edit / Format / Paragraph / View / Help)."""
        menubar = Gio.Menu()

        # ── File ──
        file_menu = Gio.Menu()
        file_menu.append("New File", "app.new")
        file_menu.append("Open...", "app.open")
        file_menu.append("Reopen", "app.reopen")
        file_menu.append("Save", "app.save")
        file_menu.append("Save As...", "app.save-as")
        file_menu.append("Convert...", "app.convert")
        file_menu.append("Quit", "app.quit")
        menubar.append_submenu("File", file_menu)

        # ── Edit ──
        edit_menu = Gio.Menu()
        edit_menu.append("Undo", "app.undo")
        edit_menu.append("Redo", "app.redo")
        edit_menu.append("Cut", "app.cut")
        edit_menu.append("Copy", "app.copy")
        edit_menu.append("Paste", "app.paste")
        edit_menu.append("Find...", "app.find")
        edit_menu.append("Replace...", "app.replace")
        edit_menu.append("Select All", "app.select-all")
        edit_menu.append("Remove Selection", "app.remove-selection")
        edit_menu.append("Line Up", "app.line-up")
        edit_menu.append("Line Down", "app.line-down")
        edit_menu.append("Delete Line", "app.delete-line")
        menubar.append_submenu("Edit", edit_menu)

        # ── Format ──
        fmt_menu = Gio.Menu()
        fmt_menu.append("Bold", "app.bold")
        fmt_menu.append("Italic", "app.italic")
        fmt_menu.append("Underline", "app.underline")
        fmt_menu.append("Strikethrough", "app.strikethrough")
        fmt_menu.append("Superscript", "app.superscript")
        fmt_menu.append("Subscript", "app.subscript")
        fmt_menu.append("Inline Code", "app.inline-code")
        fmt_menu.append("Mark", "app.mark")
        fmt_menu.append("Header ID...", "app.header-id")
        fmt_menu.append("Header Link...", "app.header-link")
        fmt_menu.append("Hyperlink...", "app.hyperlink")
        fmt_menu.append("Footnote...", "app.footnote")
        fmt_menu.append("Language Marker...", "app.language-marker")
        fmt_menu.append("Language Wrapping...", "app.language-wrapping")
        fmt_menu.append("Furigana...", "app.furigana")
        fmt_menu.append("Date and Time...", "app.date-time")
        fmt_menu.append("Special Mark", "app.special-mark")
        fmt_menu.append("Clear Formatting", "app.clear-formatting")

        # ── Emoji Shortcodes submenu ──
        emoji_menu = Gio.Menu()
        for emoji in EMOJIS:
            emoji_menu.append(f":{emoji}:", f"app.insert-emoji-{emoji}")
        fmt_menu.append_submenu("Emoji Shortcodes", emoji_menu)

        # ── Special Signs submenu ──
        signs_menu = Gio.Menu()
        for name, sign in SPECIAL_SIGNS:
            safe_name = name.replace(" ", "-")
            signs_menu.append(f"{sign} {name}", f"app.insert-sign-{safe_name}")
        fmt_menu.append_submenu("Special Signs", signs_menu)

        menubar.append_submenu("Format", fmt_menu)

        # ── Paragraph ──
        para_menu = Gio.Menu()
        for level in range(1, 7):
            para_menu.append(f"Heading {level}", f"app.heading-{level}")
        para_menu.append("Paragraph", "app.paragraph")
        para_menu.append("Ordered List", "app.ordered-list")
        para_menu.append("Unordered List", "app.unordered-list")
        para_menu.append("Definition List...", "app.definition-list")
        para_menu.append("Code Block...", "app.code-block")
        para_menu.append("Blockquote", "app.blockquote")
        para_menu.append("Table...", "app.table")
        para_menu.append("Image...", "app.image")
        para_menu.append("Line Break", "app.line-break")
        para_menu.append("Horizontal Rule", "app.horizontal-rule")
        para_menu.append("Add Indent", "app.add-indent")
        para_menu.append("Remove Indent", "app.remove-indent")
        para_menu.append("Comment...", "app.comment")
        para_menu.append("YAML Front Matter...", "app.yaml-front-matter")
        menubar.append_submenu("Paragraph", para_menu)

        # ── View ──
        view_menu = Gio.Menu()
        view_menu.append("Toggle Theme", "app.toggle-theme")
        view_menu.append("Editor Font...", "app.editor-font")
        view_menu.append("Zoom In", "app.zoom-in")
        view_menu.append("Zoom Out", "app.zoom-out")
        view_menu.append("Quick View", "app.quick-view")
        view_menu.append("Quick View CSS", "app.quick-view-css")
        menubar.append_submenu("View", view_menu)

        # ── Help ──
        help_menu = Gio.Menu()
        help_menu.append("Markdown Guide", "app.help-markdown-guide")
        help_menu.append("About Editor", "app.help-about")
        menubar.append_submenu("Help", help_menu)

        return menubar

    def _build_menu_model(self) -> Gio.Menu:
        """Return the hamburger menu model (compact subset of the menu bar)."""
        menu = Gio.Menu()
        section = Gio.Menu()
        section.append("New File", "app.new")
        section.append("Open...", "app.open")
        section.append("Save", "app.save")
        section.append("Save As...", "app.save-as")
        menu.append_section(None, section)

        section2 = Gio.Menu()
        section2.append("Find...", "app.find")
        section2.append("Replace...", "app.replace")
        section2.append("Select All", "app.select-all")
        menu.append_section(None, section2)

        section3 = Gio.Menu()
        section3.append("Toggle Theme", "app.toggle-theme")
        section3.append("About Editor", "app.help-about")
        menu.append_section(None, section3)
        return menu

    # ------------------------------------------------------------------
    # Title bar & status
    # ------------------------------------------------------------------

    def _update_title(self) -> None:
        """Refresh the window title to reflect current file name and modification state."""
        symbol = "*" if self.is_modified else ""
        name = self.current_file.name if self.current_file else "New File"
        self.set_title(f"{APP_NAME} - {symbol}{name}")

    def _update_status(self) -> None:
        """Update the status-bar label with the current cursor line and column."""
        try:
            cursor = self._editor.get_cursor_iter()
            line = cursor.get_line() + 1
            col = cursor.get_line_offset() + 1
            self._status_label.set_text(f"Ln {line}, Col {col}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Change tracking
    # ------------------------------------------------------------------

    def _on_editor_modified(self, buf: GtkSource.Buffer) -> None:
        """Handle the buffer's modified-changed signal."""
        if not buf.get_modified():
            return
        self.is_modified = True
        self._update_title()

    def _on_editor_changed(self, buf: GtkSource.Buffer) -> None:
        """Schedule an idle update when the buffer content changes."""
        if not self._idle_update_pending:
            self._idle_update_pending = True
            GLib.idle_add(self._do_editor_update)

    def _do_editor_update(self) -> bool:
        """Perform the idle callback: update status bar and auto-save temp file."""
        self._idle_update_pending = False
        self._update_status()
        # Auto-save to temp file
        text = self._editor.get_text()
        save_temp_md(text, self.current_file)
        return False

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _check_save(self, callback) -> None:
        """Prompt the user to save unsaved changes before proceeding.

        *callback* is called with True (proceed) or False (cancel) once the
        user answers.  Uses ``Gtk.AlertDialog`` which is non-blocking.
        """
        if not self.is_modified:
            callback(True)
            return
        alert = Gtk.AlertDialog()
        alert.set_message("Save changes")
        alert.set_detail("Save the opened file?")
        alert.add_button("_Cancel", 0)
        alert.add_button("_Yes", 1)
        alert.add_button("_No", 2)
        alert.set_cancel_button(0)
        alert.set_default_button(1)

        def on_response(dlg, res):
            """Handle alert dialog response."""
            try:
                choice = dlg.choose_finish(res)
                callback(choice != 0)
            except GLib.Error:
                callback(False)

        alert.choose(self, None, on_response)

    def _on_new(self) -> None:
        """Clear the editor and reset to an empty untitled document."""
        self._editor.clear()
        self.current_file = None
        self.is_modified = False
        self._update_title()
        self._editor.focus()

    def _on_open(self) -> None:
        """Open a file-chooser dialog to load a Markdown file."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Open file")
        f = Gtk.FileFilter()
        f.set_name("Markdown files")
        f.add_pattern("*.md")
        f.add_pattern("*.markdown")
        f2 = Gtk.FileFilter()
        f2.set_name("All files")
        f2.add_pattern("*")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(f)
        filters.append(f2)
        dialog.set_filters(filters)
        dialog.open(self, None, self._on_open_response)

    def _on_open_response(self, dialog, result) -> None:
        """Handle the result of the Open file dialog."""
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return
        if file is None:
            return
        try:
            text = file.load_contents(None)[1].decode("utf-8")
        except Exception as exc:
            show_message(self, "Open file", str(exc), "error")
            return
        self._editor.set_text(text)
        self.current_file = Path(file.get_path())
        self.is_modified = False
        self._update_title()

    def _on_reopen(self) -> None:
        """Reload the current file from disk, discarding unsaved changes."""
        if not self.current_file:
            return
        try:
            text = self.current_file.read_text(encoding="utf-8")
        except Exception as exc:
            show_message(self, "Reopen file", str(exc), "error")
            return
        self._editor.set_text(text)
        self.is_modified = False
        self._update_title()
        show_message(self, "Reopen file", "File reopened!")

    def _on_save(self) -> bool:
        """Save to the current file, or fall back to Save As if untitled."""
        if self.current_file:
            self._save_to(self.current_file)
            return True
        return self._on_save_as()

    def _save_to(self, path: Path) -> None:
        """Write the editor content to *path* and update modification state."""
        try:
            text = self._editor.get_text()
            path.write_text(text, encoding="utf-8")
            self.current_file = path
            self.is_modified = False
            self._editor.set_modified(False)
            self._update_title()
            # Clean up temp files with ~ prefix
            cleanup_tilde_files(path.parent)
        except Exception as exc:
            show_message(self, "Save file", str(exc), "error")
            return
        show_message(self, "Save file", "File saved!")

    def _on_save_as(self) -> bool:
        """Open a file-chooser dialog to save under a new name."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Save As")
        f = Gtk.FileFilter()
        f.set_name("Markdown files")
        f.add_pattern("*.md")
        f.add_pattern("*.markdown")
        f2 = Gtk.FileFilter()
        f2.set_name("All files")
        f2.add_pattern("*")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(f)
        filters.append(f2)
        dialog.set_filters(filters)

        initial = self.current_file.name if self.current_file else "untitled.md"
        dialog.set_initial_name(initial)
        dialog.save(self, None, self._on_save_as_response)
        return True

    def _on_save_as_response(self, dialog, result) -> None:
        """Handle the result of the Save As file dialog."""
        try:
            file = dialog.save_finish(result)
        except GLib.Error:
            return
        if file is None:
            return
        path = Path(file.get_path())
        if not path.suffix:
            path = path.with_suffix(".md")
        self._save_to(path)

    def _on_convert(self) -> None:
        """Show the format chooser then a file dialog for export."""
        formats = [
            "HTML5 file (.html)",
            "HTML5 file with CSS3 (.html)",
            "Plain text file (.txt)",
            "PDF file (.pdf)",
        ]
        dlg = ChoiceDialog(
            self, prompt="Choose the target format:", items=formats, initial=formats[0]
        )
        dlg.connect("closed", lambda _: self._convert_after_choice(dlg.result, formats))
        dlg.present()

    def _convert_after_choice(self, choice: str | None, formats: list[str]) -> None:
        """Show the file-save dialog after the user picks an export format."""
        if not choice:
            return
        if choice.startswith("HTML5 file with"):
            ext, include_css = ".html", True
        elif choice.startswith("HTML5"):
            ext, include_css = ".html", False
        elif choice.startswith("Plain"):
            ext, include_css = ".txt", False
        else:
            ext, include_css = ".pdf", False

        f = Gtk.FileFilter()
        f.set_name(
            f"{'HTML5' if ext == '.html' else 'Text' if ext == '.txt' else 'PDF'} files"
        )
        f.add_pattern(f"*{ext}")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(f)

        base = self.current_file.name if self.current_file else "document"
        if base.endswith((".md", ".markdown")):
            base = base.rsplit(".", 1)[0]

        dialog = Gtk.FileDialog()
        dialog.set_title("Convert")
        dialog.set_initial_name(base + ext)
        dialog.set_filters(filters)
        dialog.save(
            self,
            None,
            lambda d, r: self._perform_convert_response(d, r, ext, include_css),
        )

    def _perform_convert_response(
        self, dialog, result, ext: str, include_css: bool
    ) -> None:
        """Handle the result of the Convert file dialog and perform the export."""
        try:
            file = dialog.save_finish(result)
        except GLib.Error:
            return
        if file is None:
            return
        path = Path(file.get_path())
        try:
            content = self._editor.get_text()
            if ext == ".html":
                html = md_to_html(content, include_css=include_css)
                path.write_text(html, encoding="utf-8")
            elif ext == ".txt":
                path.write_text(md_to_plain(content), encoding="utf-8")
            else:
                md_to_pdf(content, str(path))
        except Exception as exc:
            show_message(self, "Convert", str(exc), "error")
            return
        show_message(self, "Convert", "Conversion complete!")

    def _on_quit(self) -> None:
        """Clean up temp files and close the application window."""
        # Clean up temp files in the working directory
        if self.current_file:
            cleanup_tilde_files(self.current_file.parent)
        else:
            cleanup_tilde_files(ensure_cache_dir())
        self.close()

    # ------------------------------------------------------------------
    # Edit operations
    # ------------------------------------------------------------------

    def _on_undo(self) -> None:
        """Undo the last editing action."""
        self._editor.undo()

    def _on_redo(self) -> None:
        """Redo the last undone editing action."""
        self._editor.redo()

    def _on_cut(self) -> None:
        """Cut the selection to the clipboard."""
        clipboard = Gdk.Display.get_default().get_clipboard()
        text = self._editor.get_selected_text()
        if text:
            clipboard.set(text)
            self._editor.delete_selection()

    def _on_copy(self) -> None:
        """Copy the selection to the clipboard."""
        clipboard = Gdk.Display.get_default().get_clipboard()
        text = self._editor.get_selected_text()
        if text:
            clipboard.set(text)

    def _on_paste(self) -> None:
        """Paste text from the clipboard asynchronously."""
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.read_text_async(None, self._on_paste_text)

    def _on_paste_text(self, clipboard, result) -> None:
        """Handle the asynchronous clipboard text read result."""
        try:
            text = clipboard.read_text_finish(result)
        except GLib.Error:
            return
        if text:
            self._editor.replace_selection(text)

    def _on_select_all(self) -> None:
        """Select the entire document."""
        self._editor.select_all()

    def _on_remove_selection(self) -> None:
        """Deselect the current selection without modifying the text."""
        buf = self._editor.get_buffer()
        buf.place_cursor(buf.get_iter_at_mark(buf.get_insert()))
        self._editor.focus()

    def _on_line_up(self) -> None:
        """Swap the current line with the one above it."""
        line = self._editor.get_current_line_number()
        if line <= 1:
            return
        buf = self._editor.get_buffer()
        cur_text = self._editor.get_line_text(line)
        prev_text = self._editor.get_line_text(line - 1)
        buf.begin_user_action()
        self._editor.replace_line(line - 1, cur_text)
        self._editor.replace_line(line, prev_text)
        buf.end_user_action()

    def _on_line_down(self) -> None:
        """Swap the current line with the one below it."""
        line = self._editor.get_current_line_number()
        total = self._editor.get_line_count()
        if line >= total:
            return
        buf = self._editor.get_buffer()
        cur_text = self._editor.get_line_text(line)
        next_text = self._editor.get_line_text(line + 1)
        buf.begin_user_action()
        self._editor.replace_line(line, next_text)
        self._editor.replace_line(line + 1, cur_text)
        buf.end_user_action()

    def _on_delete_line(self) -> None:
        """Delete the entire line at the cursor position."""
        line = self._editor.get_current_line_number()
        buf = self._editor.get_buffer()
        total = buf.get_line_count()
        _, start = buf.get_iter_at_line(line - 1)
        if line < total:
            # Non-last line: end iterator sits at the start of the next line,
            # which includes the trailing '\n' of the current line.
            _, end = buf.get_iter_at_line(line)
        else:
            # Last line: advance to the very end of the buffer.
            end = buf.get_end_iter()
        buf.begin_user_action()
        buf.delete(start, end)
        buf.end_user_action()

    def _on_find(self) -> None:
        """Open the Find dialog."""
        dlg = FindDialog(self, self._editor)
        dlg.present()

    def _on_replace(self) -> None:
        """Open the Find & Replace dialog."""
        dlg = ReplaceDialog(self, self._editor)
        dlg.present()

    # ------------------------------------------------------------------
    # Format operations
    # ------------------------------------------------------------------

    def _insert_text(self, text: str) -> None:
        """Insert *text* at the cursor and return focus to the editor."""
        self._editor.insert_at_cursor(text)
        self._editor.focus()

    def _wrap_selection(self, wrapper: str) -> None:
        """Wrap the selection with *wrapper* characters (e.g. ``**`` for bold)."""
        self._editor.wrap_selection(wrapper)
        self._editor.focus()

    def _on_bold(self) -> None:
        """Toggle bold formatting around the selection."""
        self._wrap_selection("**")

    def _on_italic(self) -> None:
        """Toggle italic formatting around the selection."""
        self._wrap_selection("*")

    def _on_underline(self) -> None:
        """Toggle underline formatting around the selection."""
        self._wrap_selection("^^")

    def _on_strikethrough(self) -> None:
        """Toggle strikethrough formatting around the selection."""
        self._wrap_selection("~~")

    def _on_superscript(self) -> None:
        """Toggle superscript formatting around the selection."""
        self._wrap_selection("^")

    def _on_subscript(self) -> None:
        """Toggle subscript formatting around the selection."""
        self._wrap_selection("~")

    def _on_inline_code(self) -> None:
        """Toggle inline code formatting around the selection."""
        self._wrap_selection("`")

    def _on_mark(self) -> None:
        """Toggle mark (highlight) formatting around the selection."""
        self._wrap_selection("==")

    def _on_header_id(self) -> None:
        """Prompt for a header ID and append it to the current heading line."""
        line_num = self._editor.get_current_line_number()
        line = self._editor.get_line_text(line_num)

        def on_hid(hid):
            """Handle header ID input."""
            if not hid:
                return
            hid = hid.strip().lstrip("#")
            if line.strip():
                self._editor.replace_line(line_num, f"{line.rstrip()} {{#{hid}}}")
            else:
                self._editor.replace_line(line_num, f"# {{#{hid}}}")

        ask_string(self, "Enter the header ID (without #):", "Header ID", on_hid)

    def _on_header_link(self) -> None:
        """Open the Header Link dialog to insert a heading cross-reference."""
        dlg = HeaderLinkDialog(self, self._insert_text)
        dlg.present()

    def _on_hyperlink(self) -> None:
        """Prompt for URL and text, then insert a Markdown hyperlink."""
        selected = self._editor.get_selected_text()

        def on_url(url):
            """Handle URL input."""
            if not url:
                return

            def on_text(text):
                """Handle link text input."""
                if selected:
                    self._editor.replace_selection(f"[{text}]({url})")
                else:
                    self._editor.insert_at_cursor(f"[{text}]({url})")
                self._editor.focus()

            if selected:
                on_text(selected)
            else:
                ask_string(self, "Enter the link text:", "Hyperlink", on_text)

        ask_string(self, "Enter the URL:", "Hyperlink", on_url)

    def _on_footnote(self) -> None:
        """Open the Footnote dialog to insert a reference and optional definition."""

        def callback(ref, definition):
            """Handle footnote input."""
            self._editor.insert_at_cursor(f"[^{ref}]")
            if definition:
                buf = self._editor.get_buffer()
                end = buf.get_end_iter()
                buf.insert(end, f"\n\n[^{ref}]: {definition}")
            self._editor.focus()

        dlg = FootnoteDialog(self, callback)
        dlg.present()

    def _on_language_marker(self) -> None:
        """Prepend a language marker tag (e.g. ``:de``) to the current line."""

        def on_lang(lang):
            """Handle language marker input."""
            if not lang:
                return
            lang = lang.strip()
            line_num = self._editor.get_current_line_number()
            line = self._editor.get_line_text(line_num)
            self._editor.replace_line(line_num, f"{{:{lang}}} {line}")
            self._editor.focus()

        ask_string(
            self,
            "or enter a valid BCP 47 tag:",
            "Language Marker",
            on_lang,
            options=LANGUAGE_TAGS,
        )

    def _on_language_wrapping(self) -> None:
        """Wrap the selection with a language tag pair (e.g. ``{:fr}…{:}``)."""

        def on_lang(lang):
            """Handle language wrapping input."""
            if not lang:
                return
            lang = lang.strip()
            selected = self._editor.get_selected_text()
            if selected:
                self._editor.replace_selection(
                    "{" + f":{lang}" + "}" + selected + "{:}"
                )
            else:
                self._editor.insert_at_cursor("{" + f":{lang}" + "}{:}")
            self._editor.focus()

        ask_string(
            self,
            "or enter a valid BCP 47 tag:",
            "Language Wrapping",
            on_lang,
            options=LANGUAGE_TAGS,
        )

    def _on_furigana(self) -> None:
        """Open the Furigana dialog to insert a ruby annotation."""
        dlg = FuriganaDialog(self, self._insert_text)
        dlg.present()

    def _on_date_time(self) -> None:
        """Open the Date & Time dialog to insert a formatted timestamp."""
        dlg = DateTimeDialog(self, self._insert_text)
        dlg.present()

    def _on_special_mark(self) -> None:
        """Insert a backslash escape character."""
        self._editor.insert_at_cursor("\\")
        self._editor.focus()

    def _on_clear_formatting(self) -> None:
        """Strip all Markdown syntax from the document, producing plain text."""
        text = self._editor.get_text()
        cleaned = md_to_plain(text)
        self._editor.set_text(cleaned)

    # ------------------------------------------------------------------
    # Paragraph operations
    # ------------------------------------------------------------------

    def _get_current_line_text(self) -> str:
        """Return the text of the line at the cursor (without the trailing newline)."""
        return self._editor.get_line_text(self._editor.get_current_line_number())

    def _replace_current_line(self, new_text: str) -> None:
        """Replace the content of the line at the cursor with *new_text*."""
        self._editor.replace_line(self._editor.get_current_line_number(), new_text)

    def _add_blank_line_before_if_needed(self) -> None:
        """Insert a blank line before the current line when the previous line is non-empty."""
        line = self._editor.get_current_line_number()
        if line <= 1:
            return
        prev = self._editor.get_line_text(line - 1)
        if prev.strip():
            buf = self._editor.get_buffer()
            _, insert_pos = buf.get_iter_at_line(line - 1)
            buf.begin_user_action()
            buf.insert(insert_pos, "\n")
            buf.end_user_action()

    def _on_heading(self, level: int) -> None:
        """Set the current line as a heading of the given *level* (1-6)."""
        text = self._get_current_line_text()
        text = re.sub(r"^#{1,6}\s*", "", text)
        self._add_blank_line_before_if_needed()
        self._replace_current_line(f"{'#' * level} {text}")

    def _on_paragraph(self) -> None:
        """Convert the current heading line to a normal paragraph."""
        text = self._get_current_line_text()
        text = re.sub(r"^#{1,6}\s*", "", text)
        self._add_blank_line_before_if_needed()
        self._replace_current_line(text)

    def _on_ordered_list(self) -> None:
        """Convert the current line to an ordered-list item (``1. …``)."""
        text = self._get_current_line_text()
        text = re.sub(r"^(\d+\.|\*|-|>)\s*", "", text)
        self._add_blank_line_before_if_needed()
        self._replace_current_line(f"1. {text}")

    def _on_unordered_list(self) -> None:
        """Convert the current line to an unordered-list item (``* …``)."""
        text = self._get_current_line_text()
        text = re.sub(r"^(\d+\.|\*|-|>)\s*", "", text)
        self._add_blank_line_before_if_needed()
        self._replace_current_line(f"* {text}")

    def _on_definition_list(self) -> None:
        """Open the Definition List dialog to insert a term/definition block."""
        dlg = DefinitionListDialog(self, self._insert_block)
        dlg.present()

    def _on_code_block(self) -> None:
        """Prompt for a language tag and wrap the current line in a fenced code block."""

        def on_lang(lang):
            """Handle code block language input."""
            lang = (lang or "").strip()
            text = self._get_current_line_text()
            self._add_blank_line_before_if_needed()
            self._replace_current_line(f"```{lang}\n{text}\n```")

        ask_string(
            self, "Enter the programming language (optional):", "Code Block", on_lang
        )

    def _on_blockquote(self) -> None:
        """Prefix the current line with ``> `` to make it a blockquote."""
        text = self._get_current_line_text()
        text = re.sub(r"^>\s*", "", text)
        self._add_blank_line_before_if_needed()
        self._replace_current_line(f"> {text}")

    def _on_table(self) -> None:
        """Open the Table dialog to insert a Markdown table."""
        dlg = TableDialog(self, self._insert_block)
        dlg.present()

    def _on_image(self) -> None:
        """Open a file chooser for an image, then prompt for alt text and title."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Choose an image")
        f = Gtk.FileFilter()
        f.set_name("Images")
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.svg", "*.webp"):
            f.add_pattern(ext)
        f2 = Gtk.FileFilter()
        f2.set_name("All files")
        f2.add_pattern("*")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(f)
        filters.append(f2)
        dialog.set_filters(filters)
        dialog.open(self, None, self._on_image_response)

    def _on_image_response(self, dialog, result) -> None:
        """Handle the result of the image file chooser dialog."""
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return
        if file is None:
            return
        path = file.get_path()

        def on_alt(alt):
            """Handle alt text input."""
            alt = (alt or "").strip()

            def on_title(title):
                """Handle image title input."""
                title = (title or "").strip()
                if title:
                    markdown = f'![{alt}]({path} "{title}")'
                else:
                    markdown = f"![{alt}]({path})"
                self._add_blank_line_before_if_needed()
                self._insert_block(markdown)

            ask_string(
                self, "Enter an Optional title (or leave empty):", "Image", on_title
            )

        ask_string(self, "Enter the Alt text:", "Image", on_alt)

    def _on_line_break(self) -> None:
        """Insert a Markdown hard line break (two trailing spaces + newline)."""
        self._editor.insert_at_cursor("  \n")
        self._editor.focus()

    def _on_horizontal_rule(self) -> None:
        """Insert a horizontal rule (``***``)."""
        self._insert_block("***")

    def _on_add_indent(self) -> None:
        """Indent the current line by two spaces."""
        line = self._editor.get_current_line_number()
        buf = self._editor.get_buffer()
        _, pos = buf.get_iter_at_line(line - 1)
        buf.begin_user_action()
        buf.insert(pos, "  ")
        buf.end_user_action()

    def _on_remove_indent(self) -> None:
        """Remove up to two leading spaces from the current line."""
        line = self._editor.get_current_line_number()
        text = self._editor.get_line_text(line)
        if text.startswith("  "):
            self._editor.replace_line(line, text[2:])
        elif text.startswith(" "):
            self._editor.replace_line(line, text[1:])

    def _on_comment(self) -> None:
        """Prompt for text and insert a hidden comment block (``[text]: #``)."""

        def on_comment(comment):
            """Handle comment input."""
            if comment is None:
                return
            self._insert_block(f"[{comment}]: #")

        ask_string(self, "Enter the comment text:", "Comment", on_comment)

    def _on_yaml_front_matter(self) -> None:
        """Open the YAML Front Matter dialog and prepend the metadata block."""

        def callback(block):
            """Handle YAML front matter block."""
            text = self._editor.get_text()
            if text.startswith("---"):
                show_message(
                    self,
                    "YAML Front Matter",
                    "The document already has a YAML Front Matter block.",
                    "warning",
                )
                return
            buf = self._editor.get_buffer()
            start = buf.get_start_iter()
            buf.begin_user_action()
            buf.insert(start, block + "\n\n")
            buf.end_user_action()
            self._editor.focus()

        dlg = YAMLFrontMatterDialog(self, callback)
        dlg.present()

    def _insert_block(self, text: str) -> None:
        """Insert *text* as a block (with a leading blank line) at the cursor."""
        self._add_blank_line_before_if_needed()
        self._editor.insert_at_cursor(text + "\n")
        self._editor.focus()

    # ------------------------------------------------------------------
    # View operations
    # ------------------------------------------------------------------

    def _on_toggle_theme(self) -> None:
        """Switch between light and dark appearance modes."""
        new = "dark" if self._theme_mode == "light" else "light"
        self._apply_theme(new)

    def _on_editor_font(self) -> None:
        """Open the font chooser to change the editor font family and size."""
        dialog = Gtk.FontDialog()
        dialog.set_title("Choose Editor Font")
        font_desc = Pango.FontDescription.from_string(
            f"Noto Sans Mono {self.editor_font_size}"
        )
        dialog.choose_font(self, font_desc, None, self._on_editor_font_response)

    def _on_editor_font_response(self, dialog, result) -> None:
        """Handle the result of the font chooser dialog."""
        try:
            font_desc = dialog.choose_font_finish(result)
        except GLib.Error:
            return
        if font_desc:
            family = font_desc.get_family()
            size = font_desc.get_size()
            if size > 0:
                self.editor_font_size = size // Pango.SCALE
            self._editor_font_family = family
            self._editor.set_font_family(family)
            self._editor.set_font_size(self.editor_font_size)
            save_font(family, self.editor_font_size)

    def _apply_theme(self, name: str) -> None:
        """Apply the named theme ('light' or 'dark') and persist the choice."""
        name = name.lower()
        if name not in THEMES:
            return
        settings = Gtk.Settings.get_default()
        if name == "dark":
            settings.set_property("gtk-application-prefer-dark-theme", True)
            self._status_label.add_css_class("dark")
        else:
            settings.set_property("gtk-application-prefer-dark-theme", False)
            self._status_label.remove_css_class("dark")
        self._theme_mode = name
        self._editor.set_mode(name)
        save_theme(name)

    def _on_zoom_in(self) -> None:
        """Increase the editor font size by two points and persist."""
        self.editor_font_size = max(8, self.editor_font_size + 2)
        self._editor.set_font_size(self.editor_font_size)
        save_font(self._editor_font_family, self.editor_font_size)

    def _on_zoom_out(self) -> None:
        """Decrease the editor font size by two points and persist."""
        self.editor_font_size = max(8, self.editor_font_size - 2)
        self._editor.set_font_size(self.editor_font_size)
        save_font(self._editor_font_family, self.editor_font_size)

    def _on_quick_view(self) -> None:
        """Render the document as HTML5 and open it in the default browser."""
        self._quick_view(include_css=False)

    def _on_quick_view_css(self) -> None:
        """Render the document as HTML5 with embedded CSS and open in the browser."""
        self._quick_view(include_css=True)

    def _quick_view(self, include_css: bool) -> None:
        """Quick view: save temp MD for saved files, then create HTML."""
        content = self._editor.get_text()
        # For saved files, save temp MD with ~ prefix first
        if self.current_file:
            save_temp_md(content, self.current_file)
        # Create HTML temp file
        try:
            html = md_to_html(content, include_css=include_css)
            html_path = save_temp_html(html, self.current_file)
        except Exception as exc:
            show_message(self, "Quick View", str(exc), "error")
            return
        webbrowser.open(html_path.as_uri())

    # ------------------------------------------------------------------
    # Help
    # ------------------------------------------------------------------

    def _on_help_markdown_guide(self) -> None:
        """Open the Markdown Guide website in the default browser."""
        webbrowser.open("https://www.markdownguide.org/")

    def _on_help_about(self) -> None:
        """Show the About dialog with version and release information."""
        from mark_editor.constants import RELEASE

        dlg = AboutDialog(self, APP_NAME, VERSION, RELEASE)
        dlg.present()

    # ------------------------------------------------------------------
    # Theme restore
    # ------------------------------------------------------------------

    def _restore_pending_text(self) -> None:
        """Restore any unsaved text from the previous session (cached temp file)."""
        text = load_temp_md(None)
        if text and text.strip():
            self._editor.set_text(text)
            self.is_modified = True
            self._update_title()
