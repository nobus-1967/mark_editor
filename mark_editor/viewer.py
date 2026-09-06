"""GTK4 WebKit viewer window for quick document previews."""

from __future__ import annotations

import contextlib
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")

from gi.repository import Gtk, WebKit


class QuickViewWindow(Gtk.Window):
    """A standalone window that renders local HTML in a WebKit.WebView.

    Defaults are chosen for quick Markdown previews: universal file access and
    same-origin file access are enabled so the generated temp HTML can request
    assets (CSS, images) from outside its own parent folder tree.  The temp
    HTML file is deleted when the window is closed.
    """

    def __init__(
        self,
        uri: str,
        *,
        title: str = "Quick View",
        html_path: Path | None = None,
        width: int = 1024,
        height: int = 768,
    ) -> None:
        """Initialize and load *uri* into a new quick-view window."""
        super().__init__()
        self.set_title(title)
        self.set_default_size(width, height)
        self._html_path = html_path
        self.connect("close-request", self._on_close_request)
        self.connect("destroy", self._on_destroy)

        web_view = WebKit.WebView()
        settings = web_view.get_settings()
        settings.set_allow_universal_access_from_file_urls(True)
        settings.set_allow_file_access_from_file_urls(True)
        web_view.load_uri(uri)

        self.set_child(web_view)
        self.present()

    def _delete_temp_html(self) -> None:
        """Delete the temporary HTML file, ignoring any errors."""
        if self._html_path is not None:
            with contextlib.suppress(Exception):
                self._html_path.unlink(missing_ok=True)

    def _on_close_request(self, _widget) -> bool:
        """Delete the temporary HTML file when the window is closed.

        Returns ``False`` to allow the default close behaviour (a GTK4 toplevel
        window is hidden on close; the ``destroy`` signal fires later during
        teardown, so ``close-request`` is the reliable place to clean up).
        """
        self._delete_temp_html()
        return False

    def _on_destroy(self, _widget) -> None:
        """Remove the temporary HTML file if the window is destroyed directly."""
        self._delete_temp_html()
