"""Mark Editor -- entry point."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib


def main() -> None:
    """Entry point: suppress harmless GTK4 layout warnings, then launch the app."""

    # Suppress harmless GTK4 layout warnings during initial rendering
    def _log_handler(domain, level, message, user_data):
        """Suppress harmless GTK4 layout warnings."""
        if "snapshot" in message.lower() or "allocation" in message.lower():
            return  # suppress
        GLib.log_default_handler(domain, level, message, user_data)

    GLib.log_set_handler("Gtk", GLib.LogLevelFlags.LEVEL_WARNING, _log_handler, None)

    from mark_editor.application import MarkEditorApp

    app = MarkEditorApp()
    sys.exit(app.run(sys.argv))


if __name__ == "__main__":
    main()
