"""Platform-agnostic global hotkey handling.

The real work lives in a per-platform backend exposing a
``HotkeyListenerThread(hotkey_str, callback)`` with ``start()``, ``stop()``,
``hotkey_str`` and ``error``.
"""

import sys
import logging

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger("livedot.input")

if sys.platform == "win32":
    from input_win32 import HotkeyListenerThread
else:
    from input_x11 import HotkeyListenerThread


class InputManager(QObject):
    # Emitted from the listener thread; Qt queues it onto the GUI thread,
    # so connected slots never run inside the X11 loop or a Windows hook.
    triggered = pyqtSignal()

    def __init__(self, state_manager):
        super().__init__()
        self.state_manager = state_manager
        self.listener_thread = None

        # Recreate the listener when the hotkey changes in config
        self.state_manager.config_saved.connect(self.sync_listener_hotkey)

        # Start initial listener
        self.start_listener()

    def start_listener(self):
        hotkey = self.state_manager.config["app_hotkey"]
        self.listener_thread = HotkeyListenerThread(hotkey, self.triggered.emit)
        self.listener_thread.start()

    def sync_listener_hotkey(self):
        """Recreates the listener thread if the app hotkey changed in config."""
        new_hotkey = self.state_manager.config["app_hotkey"]
        if self.listener_thread and self.listener_thread.hotkey_str != new_hotkey:
            logger.info("Hotkey changed in config. Recreating listener thread...")
            self.listener_thread.stop()
            self.start_listener()

    def status_error(self):
        """Returns a human-readable problem with the hotkey, or None.

        A hotkey the OS refuses to register looks exactly like "the app does
        nothing" from the outside, so the menu surfaces it.
        """
        if self.listener_thread is not None:
            return self.listener_thread.error
        return None

    def close(self):
        if self.listener_thread:
            self.listener_thread.stop()
