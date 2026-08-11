"""Platform-agnostic global hotkey handling.

The real work lives in a per-platform backend exposing three things:
an ``InputBackend`` with ``create_listener()``, ``send_hotkey()`` and ``close()``.
"""

import sys
import logging

logger = logging.getLogger("livedot.input")

if sys.platform == "win32":
    from input_win32 import InputBackend
else:
    from input_x11 import InputBackend


class InputManager:
    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.backend = InputBackend()
        self.listener_thread = None

        # Connect to state manager config changes
        self.state_manager.config_saved.connect(self.sync_listener_hotkey)
        # Connect to state changes to forward the hotkey to Discord on clicks/hotkeys
        self.state_manager.state_changed.connect(self.on_state_changed)

        # Start initial listener
        self.start_listener()

    def start_listener(self):
        hotkey = self.state_manager.config["app_hotkey"]
        self.listener_thread = self.backend.create_listener(hotkey, self.on_hotkey_triggered)
        self.listener_thread.start()

    def sync_listener_hotkey(self):
        """Recreates the listener thread if the app hotkey changed in config."""
        new_hotkey = self.state_manager.config["app_hotkey"]
        if self.listener_thread and self.listener_thread.hotkey_str != new_hotkey:
            logger.info("Hotkey changed in config. Recreating listener thread...")
            self.listener_thread.stop()
            self.start_listener()

    def on_hotkey_triggered(self):
        """Callback from hotkey thread. Toggles state."""
        self.state_manager.toggle_mute()

    def on_state_changed(self, is_muted: bool):
        """Called whenever the state changes (via hotkey or mouse click) to forward key."""
        self.forward_discord_hotkey()

    def forward_discord_hotkey(self):
        self.backend.send_hotkey(self.state_manager.config["discord_hotkey"])

    def status_error(self):
        """Returns a human-readable problem with the hotkeys, or None.

        Both halves fail silently into the log otherwise: a hotkey the OS
        refuses to register and a forward the OS refuses to deliver look exactly
        like "the app does nothing" from the outside.
        """
        if self.listener_thread is not None and self.listener_thread.error:
            return self.listener_thread.error
        return getattr(self.backend, "last_error", None)

    def close(self):
        if self.listener_thread:
            self.listener_thread.stop()
        self.backend.close()
