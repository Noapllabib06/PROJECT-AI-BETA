"""UI Launcher and Desktop Window Manager for JARVIS.

Supports launching the interface via native desktop window (pywebview) or default web browser.
"""

import sys
import webbrowser
import threading
import time
from typing import Optional
from config.settings import get_logger

logger = get_logger("UI")


class DesktopWindowAPI:
    """Exposes window control methods to pywebview javascript context."""

    def __init__(self, window=None):
        self._window = window

    def set_window(self, window):
        self._window = window

    def minimize(self):
        if self._window:
            self._window.minimize()

    def maximize(self):
        if self._window:
            self._window.toggle_fullscreen()

    def close(self):
        if self._window:
            self._window.destroy()


def launch_desktop_window(
    url: str,
    title: str = "Jarvis - AI Assistant",
    width: int = 1200,
    height: int = 800,
    frameless: bool = False
) -> None:
    """Attempts to launch a native desktop window using pywebview if available,

    otherwise falls back to opening in the system default web browser.
    """
    try:
        import webview  # type: ignore

        api = DesktopWindowAPI()
        window = webview.create_window(
            title=title,
            url=url,
            width=width,
            height=height,
            min_size=(900, 600),
            frameless=frameless,
            easy_drag=frameless,
            js_api=api
        )
        api.set_window(window)
        logger.info(f"Starting PyWebView desktop GUI on {url}...")
        webview.start(debug=False)

    except ImportError:
        logger.info("pywebview not installed. Opening in default web browser instead.")
        webbrowser.open(url)
    except Exception as e:
        logger.warning(f"Failed to launch native window ({e}). Opening in default browser.")
        webbrowser.open(url)


def open_browser_delayed(url: str, delay_seconds: float = 1.0) -> None:
    """Opens the browser after a short delay to ensure FastAPI has booted."""
    def _open():
        time.sleep(delay_seconds)
        webbrowser.open(url)

    thread = threading.Thread(target=_open, daemon=True)
    thread.start()
