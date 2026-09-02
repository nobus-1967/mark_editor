"""Dialog classes for Mark Editor (GTK4 / libadwaita)."""

from __future__ import annotations

import re
from datetime import datetime

import gi

gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from mark_editor.constants import LANGUAGE_TAGS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry_row(label_text: str) -> tuple[Gtk.Label, Gtk.Entry]:
    """Create a label + entry pair for use in dialog forms."""
    label = Gtk.Label(label=label_text)
    label.set_xalign(1.0)
    entry = Gtk.Entry()
    entry.set_hexpand(True)
    return label, entry


def _make_dropdown_row(
    options: tuple[str, ...] | list[str] | None,
    entry: Gtk.Entry,
) -> Gtk.DropDown | None:
    """Create a drop-down that fills ``entry`` with the selected option.

    The default selection is ``en`` (or the first option if ``en`` is absent).
    Returns ``None`` when ``options`` is empty so callers can skip the widget.
    """
    if not options:
        return None
    combo = Gtk.DropDown.new(Gtk.StringList.new(list(options)))
    default_idx = list(options).index("en") if "en" in options else 0
    combo.set_selected(default_idx)

    def on_combo(_combo):
        """Fill the entry with the selected option."""
        selected = _combo.get_selected_item()
        if selected is not None:
            entry.set_text(selected.get_string())

    combo.connect("notify::selected-item", on_combo)
    return combo


def _dropdown_value(combo: Gtk.DropDown | None, entry_text: str) -> str | None:
    """Return the entry text, falling back to the combo's selected option."""
    text = entry_text.strip()
    if not text and combo is not None:
        selected = combo.get_selected_item()
        if selected is not None:
            text = selected.get_string()
    return text or None


def _make_button_box(*buttons: Gtk.Button) -> Gtk.Box:
    """Create a horizontally centered box containing the given buttons."""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    box.set_halign(Gtk.Align.CENTER)
    box.set_margin_top(12)
    for btn in buttons:
        box.append(btn)
    return box


def _make_button(label: str, callback=None, suggested: bool = False) -> Gtk.Button:
    """Create a button with an optional click callback and suggested-action style."""
    btn = Gtk.Button(label=label)
    if suggested:
        btn.add_css_class("suggested-action")
    if callback:
        btn.connect("clicked", callback)
    return btn


def _make_grid(
    *rows: tuple[str, Gtk.Widget], col_spacing: int = 8, row_spacing: int = 8
) -> Gtk.Grid:
    """Build a two-column grid from (label, widget) pairs."""
    grid = Gtk.Grid()
    grid.set_column_spacing(col_spacing)
    grid.set_row_spacing(row_spacing)
    for i, (label_text, widget) in enumerate(rows):
        lbl = Gtk.Label(label=label_text)
        lbl.set_xalign(1.0)
        grid.attach(lbl, 0, i, 1, 1)
        grid.attach(widget, 1, i, 1, 1)
    return grid


# ---------------------------------------------------------------------------
# Message / input helpers
# ---------------------------------------------------------------------------


def show_message(
    parent: Gtk.Window, title: str, message: str, icon: str = "info"
) -> None:
    """Display an informational alert dialog."""
    alert = Adw.AlertDialog()
    alert.set_heading(title)
    alert.set_body(message)
    if icon == "error":
        alert.set_response_appearance("destructive", Adw.ResponseAppearance.DESTRUCTIVE)
    alert.add_response("ok", "_OK")
    alert.present(parent)


def ask_string(
    parent: Gtk.Window,
    prompt: str,
    title: str,
    callback=None,
    options: tuple[str, ...] | list[str] | None = None,
) -> None:
    """Show a dialog that prompts the user for a single text input.

    If ``options`` is given, it is shown as a combo box (drop-down) above the entry;
    selecting an option fills the entry. The entry remains editable so a custom
    BCP 47 tag can be typed.
    """
    dialog = Adw.Dialog()
    dialog.set_title(title)
    dialog.set_content_width(400)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    box.set_margin_top(24)
    box.set_margin_bottom(24)
    box.set_margin_start(24)
    box.set_margin_end(24)

    entry = Gtk.Entry()
    entry.set_hexpand(True)

    combo = None
    if options:
        combo_lbl = Gtk.Label(label="Choose a language tag:")
        combo_lbl.set_xalign(0.0)
        box.append(combo_lbl)

        combo = _make_dropdown_row(options, entry)
        if combo is not None:
            box.append(combo)

    lbl = Gtk.Label(label=prompt)
    lbl.set_xalign(0.0)
    box.append(lbl)

    box.append(entry)

    result_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    result_box.set_halign(Gtk.Align.END)
    result_box.set_margin_top(8)

    cancel_btn = _make_button("Cancel")
    cancel_btn.connect("clicked", lambda _: dialog.close())
    result_box.append(cancel_btn)

    ok_btn = _make_button("OK", suggested=True)
    result_box.append(ok_btn)
    box.append(result_box)

    def on_ok(_btn):
        """Handle OK button click."""
        text = _dropdown_value(combo, entry.get_text())
        dialog.close()
        if callback:
            callback(text)

    ok_btn.connect("clicked", on_ok)
    entry.connect("activate", lambda _: on_ok(_))

    dialog.set_child(box)
    dialog.present(parent)


# ---------------------------------------------------------------------------
# Find / Replace
# ---------------------------------------------------------------------------


class FindDialog(Adw.Dialog):
    """Dialog for searching text within the editor."""

    def __init__(self, parent: Gtk.Window, editor) -> None:
        """Initialize the Find dialog with parent window and editor reference."""
        super().__init__()
        self.set_title("Find")
        self.set_content_width(420)

        self._editor = editor
        self._use_regex = False

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        self._entry = Gtk.Entry()
        self._entry.set_hexpand(True)
        self._entry.set_placeholder_text("Search text...")
        grid = _make_grid(("Find:", self._entry))
        box.append(grid)

        self._regex_check = Gtk.CheckButton(label="Use regex")
        self._regex_check.connect(
            "toggled", lambda b: setattr(self, "_use_regex", b.get_active())
        )
        box.append(self._regex_check)

        find_btn = _make_button("Find Next", self._on_find_next, suggested=True)
        close_btn = _make_button("Close", lambda _: self.close())
        box.append(_make_button_box(find_btn, close_btn))

        self._entry.connect("activate", lambda _: self._on_find_next())
        self._entry.connect("changed", self._on_search_changed)
        self.set_child(box)
        self._entry.grab_focus()

    def _on_find_next(self, *_args) -> None:
        """Find and select the next occurrence of the search term."""
        term = self._entry.get_text().strip()
        if not term:
            return
        try:
            pattern = re.compile(term if self._use_regex else re.escape(term))
        except re.error:
            return

        text = self._editor.get_text()
        cursor_offset = self._editor.get_cursor_iter().get_offset()

        match = pattern.search(text, cursor_offset)
        if not match:
            match = pattern.search(text)
        if match is None:
            return

        buf = self._editor.get_buffer()
        start = buf.get_iter_at_offset(match.start())
        end = buf.get_iter_at_offset(match.end())
        buf.select_range(start, end)
        self._editor.scroll_to_cursor()

    def _on_search_changed(self, entry) -> None:
        """Update the editor's search highlights as the user types."""
        term = entry.get_text().strip()
        self._editor.set_search_pattern(term, case_sensitive=False)

    def close(self) -> None:
        """Clear search highlights and close the dialog."""
        self._editor.clear_search()
        super().close()


class ReplaceDialog(Adw.Dialog):
    """Dialog for finding and replacing text in the editor."""

    def __init__(self, parent: Gtk.Window, editor) -> None:
        """Initialize the Replace dialog with parent window and editor reference."""
        super().__init__()
        self.set_title("Replace")
        self.set_content_width(420)

        self._editor = editor
        self._use_regex = False

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        self._find_entry = Gtk.Entry()
        self._find_entry.set_hexpand(True)
        self._replace_entry = Gtk.Entry()
        self._replace_entry.set_hexpand(True)

        grid = _make_grid(
            ("Find:", self._find_entry),
            ("Replace:", self._replace_entry),
        )
        box.append(grid)

        self._regex_check = Gtk.CheckButton(label="Use regex")
        self._regex_check.connect(
            "toggled", lambda b: setattr(self, "_use_regex", b.get_active())
        )
        box.append(self._regex_check)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_top(12)
        for label, cb in [
            ("Replace", self._on_replace),
            ("Replace All", self._on_replace_all),
            ("Find Next", self._on_find_next),
        ]:
            btn_box.append(_make_button(label, cb))
        btn_box.append(_make_button("Close", lambda _: self.close()))
        box.append(btn_box)

        self._find_entry.connect("activate", lambda _: self._on_find_next())
        self._find_entry.connect("changed", self._on_search_changed)
        self.set_child(box)
        self._find_entry.grab_focus()

    def _get_pattern(self) -> re.Pattern | None:
        """Compile the find entry text into a regex pattern, or return None."""
        term = self._find_entry.get_text()
        if not term:
            return None
        try:
            return re.compile(term if self._use_regex else re.escape(term))
        except re.error:
            return None

    def _on_find_next(self, *_args) -> None:
        """Find and select the next match of the search pattern."""
        pattern = self._get_pattern()
        if pattern is None:
            return
        text = self._editor.get_text()
        offset = self._editor.get_cursor_iter().get_offset()
        match = pattern.search(text, offset)
        if not match:
            match = pattern.search(text)
        if match is None:
            return
        buf = self._editor.get_buffer()
        buf.select_range(
            buf.get_iter_at_offset(match.start()),
            buf.get_iter_at_offset(match.end()),
        )
        self._editor.scroll_to_cursor()

    def _on_replace(self, *_args) -> None:
        """Replace the current match and advance to the next."""
        pattern = self._get_pattern()
        if pattern is None:
            return
        text = self._editor.get_text()
        offset = self._editor.get_cursor_iter().get_offset()
        match = pattern.search(text, offset)
        if not match:
            match = pattern.search(text)
        if match is None:
            return
        buf = self._editor.get_buffer()
        start = buf.get_iter_at_offset(match.start())
        end = buf.get_iter_at_offset(match.end())
        buf.begin_user_action()
        buf.delete(start, end)
        buf.insert(start, self._replace_entry.get_text(), -1)
        buf.end_user_action()

    def _on_replace_all(self, *_args) -> None:
        """Replace every occurrence of the search text in the buffer."""
        find_text = self._find_entry.get_text()
        replace_text = self._replace_entry.get_text()
        if not find_text:
            return
        self._editor.replace_all(find_text, replace_text, self._use_regex)

    def _on_search_changed(self, entry) -> None:
        """Update the editor's search highlights as the user types."""
        term = entry.get_text().strip()
        self._editor.set_search_pattern(term, case_sensitive=False)

    def close(self) -> None:
        """Clear search highlights and close the dialog."""
        self._editor.clear_search()
        super().close()


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------


class TableDialog(Adw.Dialog):
    """Dialog for inserting a Markdown table."""

    def __init__(self, parent: Gtk.Window, callback) -> None:
        """Initialize the Table dialog with parent window and callback."""
        super().__init__()
        self.set_title("Insert Table")
        self.set_content_width(380)

        self._callback = callback

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        self._cols_spin = Gtk.SpinButton()
        self._cols_spin.set_range(1, 20)
        self._cols_spin.set_value(3)
        self._rows_spin = Gtk.SpinButton()
        self._rows_spin.set_range(1, 50)
        self._rows_spin.set_value(3)

        box.append(
            _make_grid(("Columns:", self._cols_spin), ("Rows:", self._rows_spin))
        )

        self._footer_check = Gtk.CheckButton(label="Add footer")
        self._footer_check.set_active(True)
        box.append(self._footer_check)

        box.append(
            _make_button_box(
                _make_button("Insert", self._on_insert, suggested=True),
                _make_button("Cancel", lambda _: self.close()),
            )
        )
        self.set_child(box)

    def _on_insert(self, *_args) -> None:
        """Build the Markdown table string and invoke the callback."""
        cols = int(self._cols_spin.get_value())
        rows = int(self._rows_spin.get_value())
        use_footer = self._footer_check.get_active()

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
        self._callback("\n".join(lines))
        self.close()


# ---------------------------------------------------------------------------
# Furigana
# ---------------------------------------------------------------------------


class FuriganaDialog(Adw.Dialog):
    """Dialog for inserting a furigana (ruby) annotation."""

    def __init__(self, parent: Gtk.Window, callback) -> None:
        """Initialize the Furigana dialog with parent window and callback."""
        super().__init__()
        self.set_title("Furigana (Ruby Annotation)")
        self.set_content_width(380)

        self._callback = callback

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        self._kanji_entry = Gtk.Entry()
        self._kanji_entry.set_hexpand(True)
        self._reading_entry = Gtk.Entry()
        self._reading_entry.set_hexpand(True)

        box.append(
            _make_grid(
                ("Kanji / Text:", self._kanji_entry),
                ("Reading (ruby):", self._reading_entry),
            )
        )

        box.append(
            _make_button_box(
                _make_button("Insert", self._on_insert, suggested=True),
                _make_button("Cancel", lambda _: self.close()),
            )
        )

        self._kanji_entry.connect("activate", lambda _: self._on_insert())
        self._reading_entry.connect("activate", lambda _: self._on_insert())
        self.set_child(box)
        self._kanji_entry.grab_focus()

    def _on_insert(self, *_args) -> None:
        """Insert the ruby annotation and close the dialog."""
        kanji = self._kanji_entry.get_text().strip()
        reading = self._reading_entry.get_text().strip()
        if kanji and reading:
            self._callback("{" + kanji + " | " + reading + "}")
        self.close()


# ---------------------------------------------------------------------------
# Header Link
# ---------------------------------------------------------------------------


class HeaderLinkDialog(Adw.Dialog):
    """Dialog for inserting a cross-reference link to a document heading."""

    def __init__(self, parent: Gtk.Window, callback) -> None:
        """Initialize the Header Link dialog with parent window and callback."""
        super().__init__()
        self.set_title("Insert Header Link")
        self.set_content_width(380)

        self._callback = callback

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        self._id_entry = Gtk.Entry()
        self._id_entry.set_hexpand(True)
        self._text_entry = Gtk.Entry()
        self._text_entry.set_hexpand(True)

        box.append(
            _make_grid(
                ("Header ID:", self._id_entry),
                ("Link text:", self._text_entry),
            )
        )

        box.append(
            _make_button_box(
                _make_button("Insert", self._on_insert, suggested=True),
                _make_button("Cancel", lambda _: self.close()),
            )
        )

        self._id_entry.connect("activate", lambda _: self._on_insert())
        self._text_entry.connect("activate", lambda _: self._on_insert())
        self.set_child(box)
        self._id_entry.grab_focus()

    def _on_insert(self, *_args) -> None:
        """Build the heading link and invoke the callback."""
        hid = self._id_entry.get_text().strip()
        text = self._text_entry.get_text().strip() or hid
        if hid:
            self._callback(f"[{text}](#{hid})")
        self.close()


# ---------------------------------------------------------------------------
# Footnote
# ---------------------------------------------------------------------------


class FootnoteDialog(Adw.Dialog):
    """Dialog for inserting a footnote reference and optional definition."""

    def __init__(self, parent: Gtk.Window, callback) -> None:
        """Initialize the Footnote dialog with parent window and callback."""
        super().__init__()
        self.set_title("Insert Footnote")
        self.set_content_width(380)

        self._callback = callback

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        self._ref_entry = Gtk.Entry()
        self._ref_entry.set_hexpand(True)
        self._def_entry = Gtk.Entry()
        self._def_entry.set_hexpand(True)

        box.append(
            _make_grid(
                ("Reference / Name:", self._ref_entry),
                ("Definition:", self._def_entry),
            )
        )

        box.append(
            _make_button_box(
                _make_button("Insert", self._on_insert, suggested=True),
                _make_button("Cancel", lambda _: self.close()),
            )
        )

        self._ref_entry.connect("activate", lambda _: self._on_insert())
        self.set_child(box)
        self._ref_entry.grab_focus()

    def _on_insert(self, *_args) -> None:
        """Insert the footnote reference and optional definition."""
        ref = self._ref_entry.get_text().strip()
        definition = self._def_entry.get_text().strip()
        if ref:
            self._callback(ref, definition)
        self.close()


# ---------------------------------------------------------------------------
# Definition List
# ---------------------------------------------------------------------------


class DefinitionListDialog(Adw.Dialog):
    """Dialog for inserting a Markdown definition-list block."""

    def __init__(self, parent: Gtk.Window, callback) -> None:
        """Initialize the Definition List dialog with parent window and callback."""
        super().__init__()
        self.set_title("Definition List")
        self.set_content_width(400)

        self._callback = callback

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        self._term_entry = Gtk.Entry()
        self._term_entry.set_hexpand(True)
        self._def1_entry = Gtk.Entry()
        self._def1_entry.set_hexpand(True)
        self._def2_entry = Gtk.Entry()
        self._def2_entry.set_hexpand(True)

        box.append(
            _make_grid(
                ("Term:", self._term_entry),
                ("Definition 1:", self._def1_entry),
                ("Definition 2:", self._def2_entry),
            )
        )

        box.append(
            _make_button_box(
                _make_button("Insert", self._on_insert, suggested=True),
                _make_button("Cancel", lambda _: self.close()),
            )
        )
        self.set_child(box)
        self._term_entry.grab_focus()

    def _on_insert(self, *_args) -> None:
        """Build the definition-list block and invoke the callback."""
        term = self._term_entry.get_text().strip()
        defs = [
            d
            for d in (
                self._def1_entry.get_text().strip(),
                self._def2_entry.get_text().strip(),
            )
            if d
        ]
        if term and defs:
            lines = ["", term]
            lines.extend(f": {d}" for d in defs)
            self._callback("\n".join(lines))
        self.close()


# ---------------------------------------------------------------------------
# YAML Front Matter
# ---------------------------------------------------------------------------


class YAMLFrontMatterDialog(Adw.Dialog):
    """Dialog for inserting a YAML front-matter metadata block."""

    def __init__(self, parent: Gtk.Window, callback) -> None:
        """Initialize the YAML Front Matter dialog with parent window and callback."""
        super().__init__()
        self.set_title("YAML Front Matter")
        self.set_content_width(420)

        self._callback = callback

        fields = ["lang", "title", "author", "description", "keywords"]
        self._entries: dict[str, Gtk.Entry] = {}

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        grid = Gtk.Grid()
        grid.set_column_spacing(8)
        grid.set_row_spacing(8)
        self._lang_combo: Gtk.DropDown | None = None
        for i, field in enumerate(fields):
            lbl = Gtk.Label(label=f"{field}:")
            lbl.set_xalign(1.0)
            entry = Gtk.Entry()
            entry.set_hexpand(True)
            self._entries[field] = entry
            if field == "lang":
                vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                self._lang_combo = _make_dropdown_row(LANGUAGE_TAGS, entry)
                if self._lang_combo is not None:
                    vbox.append(self._lang_combo)
                vbox.append(entry)
                grid.attach(lbl, 0, i, 1, 1)
                grid.attach(vbox, 1, i, 1, 1)
                continue
            grid.attach(lbl, 0, i, 1, 1)
            grid.attach(entry, 1, i, 1, 1)
        box.append(grid)

        box.append(
            _make_button_box(
                _make_button("Insert", self._on_insert, suggested=True),
                _make_button("Cancel", lambda _: self.close()),
            )
        )
        self.set_child(box)

    def _on_insert(self, *_args) -> None:
        """Build the YAML block from filled fields and invoke the callback."""
        lines = ["---"]
        for field in ["lang", "title", "author", "description", "keywords"]:
            value = self._entries[field].get_text().strip()
            if not value and field == "lang":
                value = _dropdown_value(self._lang_combo, "") or ""
            if value:
                lines.append(f"{field}: {value}")
        lines.append(f"published: {datetime.now().date().isoformat()}")
        lines.append("---")
        self._callback("\n".join(lines))
        self.close()


# ---------------------------------------------------------------------------
# Date / Time
# ---------------------------------------------------------------------------


class DateTimeDialog(Adw.Dialog):
    """Dialog for inserting a formatted date and/or time stamp."""

    def __init__(self, parent: Gtk.Window, callback) -> None:
        """Initialize the Date & Time dialog with parent window and callback."""
        super().__init__()
        self.set_title("Insert Date and Time")
        self.set_content_width(320)

        self._callback = callback
        self._choice = "date_time"

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        group = Gtk.CheckButton()
        for label, value in [
            ("Date and time", "date_time"),
            ("Date only", "date"),
            ("Time only", "time"),
        ]:
            btn = Gtk.CheckButton(label=label, group=group)
            btn.set_active(value == "date_time")
            btn.connect(
                "toggled",
                lambda b, v=value: (
                    setattr(self, "_choice", v) if b.get_active() else None
                ),
            )
            box.append(btn)

        box.append(
            _make_button_box(
                _make_button("Insert", self._on_insert, suggested=True),
                _make_button("Cancel", lambda _: self.close()),
            )
        )
        self.set_child(box)

    def _on_insert(self, *_args) -> None:
        """Format the current date/time selection and invoke the callback."""
        now = datetime.now()
        if self._choice == "date_time":
            value = now.strftime("%Y-%m-%d %H:%M:%S")
        elif self._choice == "date":
            value = now.strftime("%Y-%m-%d")
        else:
            value = now.strftime("%H:%M:%S")
        self._callback(value)
        self.close()


# ---------------------------------------------------------------------------
# Choice (format selector)
# ---------------------------------------------------------------------------


class ChoiceDialog(Adw.Dialog):
    """Dialog for selecting an item from a drop-down list."""

    def __init__(
        self, parent: Gtk.Window, prompt: str, items: list[str], initial: str
    ) -> None:
        """Initialize the Choice dialog with prompt, items, and initial selection."""
        super().__init__()
        self.set_title("Select")
        self.set_content_width(380)

        self.result: str | None = None

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        lbl = Gtk.Label(label=prompt)
        lbl.set_xalign(0.0)
        box.append(lbl)

        self._dropdown = Gtk.DropDown()
        model = Gtk.StringList()
        for item in items:
            model.append(item)
        self._dropdown.set_model(model)
        idx = items.index(initial) if initial in items else 0
        self._dropdown.set_selected(idx)
        box.append(self._dropdown)

        box.append(
            _make_button_box(
                _make_button("OK", self._on_ok, suggested=True),
                _make_button("Cancel", lambda _: self.close()),
            )
        )
        self.set_child(box)

    def _on_ok(self, *_args) -> None:
        """Store the selected item and close the dialog."""
        model = self._dropdown.get_model()
        idx = self._dropdown.get_selected()
        if idx is not None and idx < model.get_n_items():
            self.result = model.get_string(idx)
        self.close()


# ---------------------------------------------------------------------------
# About
# ---------------------------------------------------------------------------


class AboutDialog(Adw.Dialog):
    """Dialog showing application name, version and release information."""

    def __init__(
        self, parent: Gtk.Window, app_name: str, version: str, release: str
    ) -> None:
        """Initialize the About dialog with app name, version, and release."""
        super().__init__()
        self.set_title("About")
        self.set_content_width(360)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_halign(Gtk.Align.CENTER)

        lbl = Gtk.Label(label=f"{app_name}, version {version} ({release})")
        box.append(lbl)

        close_btn = _make_button("Close", lambda _: self.close())
        close_btn.set_size_request(100, -1)
        box.append(close_btn)

        self.set_child(box)
