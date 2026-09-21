import os
import json
import math
import logging
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, QDateTime, QPoint

import constants

logger = logging.getLogger("livedot.state")

# Keys written by older versions that no longer mean anything.
OBSOLETE_KEYS = ("discord_hotkey", "sound_enabled")


class StateManager(QObject):
    # Signals to notify the UI
    state_changed = pyqtSignal()            # muted or connected changed
    visuals_updated = pyqtSignal()          # Emits whenever size/color/opacity changes
    config_saved = pyqtSignal()             # Emits when config is saved
    toggle_requested = pyqtSignal()         # A click on the dot asked to flip the mic

    def __init__(self):
        super().__init__()

        # Core runtime state, mirrored from Discord. Nothing is known until
        # the connection comes up, so the dot starts out disconnected.
        self.muted = True
        self.connected = False

        # Animated values. Opacity here excludes the user's base opacity,
        # which is applied at paint time so changes show up immediately.
        self.current_size = constants.SIZE_MUTED
        self.current_opacity = constants.OPACITY_MUTED

        # Drag details
        self.press_time = 0
        self.press_pos = QPoint()
        self.drag_started = False

        # Load configuration
        self.config = {}
        self.load_config()

        # Setup debounced save timer
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save_config)

        # Animation timeline control variables
        self.transition_t = 1.0  # 1.0 means no active transition
        self.pulse_t = 0.0

        logger.info("StateManager initialized.")

    @property
    def active(self):
        """True while the mic is known to be open."""
        return self.connected and not self.muted

    def load_config(self):
        """Loads configuration from JSON file. Falls back to defaults if not found."""
        try:
            if os.path.exists(constants.CONFIG_FILE):
                with open(constants.CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
                logger.info(f"Configuration loaded from {constants.CONFIG_FILE}")
            else:
                logger.info("Configuration file not found. Initializing defaults.")
                self.config = {}
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self.config = {}

        for key in OBSOLETE_KEYS:
            self.config.pop(key, None)

        # Set defaults for missing keys
        self.config.setdefault("position_x", 100)
        self.config.setdefault("position_y", 700)
        self.config.setdefault("scale", constants.DEFAULT_SCALE)
        self.config.setdefault("opacity", constants.DEFAULT_OPACITY)
        self.config.setdefault("app_hotkey", constants.DEFAULT_APP_HOTKEY)
        self.config.setdefault("autostart_enabled", constants.DEFAULT_AUTOSTART_ENABLED)
        self.config.setdefault("position_locked", constants.DEFAULT_POSITION_LOCKED)
        self.config.setdefault("discord_client_id", "")
        self.config.setdefault("discord_client_secret", "")
        self.config.setdefault("discord_access_token", "")
        self.config.setdefault("discord_refresh_token", "")
        self.config.setdefault("discord_token_expires", 0)

    def save_config(self):
        """Writes the configuration to disk atomically.

        The file holds the Discord client secret and tokens, so it is created
        readable by the owner only. Writing to a temporary file and renaming it
        means a crash mid-write can never leave a truncated config behind.
        """
        self.save_timer.stop()
        tmp_path = constants.CONFIG_FILE + ".tmp"
        try:
            os.makedirs(constants.CONFIG_DIR, exist_ok=True)
            fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            os.replace(tmp_path, constants.CONFIG_FILE)
            logger.info(f"Configuration saved to {constants.CONFIG_FILE}")
            self.config_saved.emit()
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")

    def save_config_debounced(self):
        """Schedules a config save, debouncing continuous events like window drags."""
        self.save_timer.start(constants.SAVE_DEBOUNCE_MS)

    def flush(self):
        """Writes a pending debounced save right away (used on exit)."""
        if self.save_timer.isActive():
            self.save_config()

    # State modification APIs
    @pyqtSlot(bool)
    def set_muted(self, muted):
        if self.muted == muted:
            return

        self.muted = muted
        logger.info(f"Microphone state changed: Muted = {self.muted}")
        self._reset_animation()
        self.state_changed.emit()

    @pyqtSlot(bool)
    def set_connected(self, connected):
        if self.connected == connected:
            return

        self.connected = connected
        logger.info(f"Discord connection changed: Connected = {self.connected}")
        self._reset_animation()
        self.state_changed.emit()

    def _reset_animation(self):
        """Starts the auto-expand when the mic opens, settles instantly otherwise."""
        self.pulse_t = 0.0
        self.current_size = constants.SIZE_MUTED
        if self.active:
            self.transition_t = 0.0
            self.current_opacity = constants.OPACITY_UNMUTED
        else:
            self.transition_t = 1.0
            self.current_opacity = constants.OPACITY_MUTED
        self.update_visuals()

    def request_toggle(self):
        self.toggle_requested.emit()

    def set_position(self, x, y):
        if self.config["position_locked"]:
            return
        if self.config["position_x"] == x and self.config["position_y"] == y:
            return
        self.config["position_x"] = x
        self.config["position_y"] = y
        self.save_config_debounced()

    def set_scale(self, scale):
        self.config["scale"] = max(0.5, min(3.0, scale))
        self.update_visuals()
        self.save_config_debounced()

    def set_opacity(self, opacity):
        self.config["opacity"] = max(0.1, min(1.0, opacity))
        self.update_visuals()
        self.save_config_debounced()

    def set_position_locked(self, locked):
        self.config["position_locked"] = locked
        self.save_config_debounced()

    def set_app_hotkey(self, hotkey):
        self.config["app_hotkey"] = hotkey
        self.save_config_debounced()

    def set_autostart_enabled(self, enabled):
        self.config["autostart_enabled"] = enabled
        self.save_config_debounced()

    def set_discord_credentials(self, client_id, client_secret):
        """Stores the Developer Portal credentials. Tokens issued for other
        credentials are useless, so they are dropped when these change."""
        if (client_id, client_secret) != (self.config["discord_client_id"],
                                          self.config["discord_client_secret"]):
            self.config["discord_client_id"] = client_id
            self.config["discord_client_secret"] = client_secret
            self.config["discord_access_token"] = ""
            self.config["discord_refresh_token"] = ""
            self.config["discord_token_expires"] = 0
            self.save_config()

    def set_discord_tokens(self, access_token, refresh_token, expires_at):
        self.config["discord_access_token"] = access_token
        self.config["discord_refresh_token"] = refresh_token
        self.config["discord_token_expires"] = int(expires_at)
        self.save_config()

    # Drag / Click Handler Methods
    def handle_mouse_press(self, global_pos: QPoint):
        self.press_time = QDateTime.currentMSecsSinceEpoch()
        self.press_pos = global_pos
        self.drag_started = False

    def handle_mouse_move(self, global_pos: QPoint):
        """Returns True when the window should follow the cursor."""
        if not self.drag_started:
            time_elapsed = QDateTime.currentMSecsSinceEpoch() - self.press_time
            delta = global_pos - self.press_pos
            distance = math.sqrt(delta.x()**2 + delta.y()**2)

            if time_elapsed >= constants.DRAG_THRESHOLD_MS and distance >= constants.DRAG_THRESHOLD_PX:
                self.drag_started = True
        # A drag on a locked dot is still a drag, not a click: it just doesn't move.
        return self.drag_started and not self.config["position_locked"]

    def handle_mouse_release(self, global_pos: QPoint):
        was_drag = self.drag_started
        self.drag_started = False
        if not was_drag:
            # Clean single click -> ask Discord to flip the mic
            self.request_toggle()
        return not was_drag

    # Animation update calculations
    def advance_time(self, dt_ms):
        """Advances the internal timers and updates current visuals based on progress."""
        if not self.active:
            # Muted or disconnected: values are static
            self.current_size = constants.SIZE_MUTED
            self.current_opacity = constants.OPACITY_MUTED
            self.transition_t = 1.0
            self.pulse_t = 0.0
            return False  # No repaint timer loop needed once settled

        # Unmuted Animation Calculations
        # 1. Handle auto-expand transition timeline
        if self.transition_t < 1.0:
            self.transition_t += dt_ms / constants.TRANSITION_DURATION_MS
            if self.transition_t >= 1.0:
                self.transition_t = 1.0

            # Easing Curve: 12px -> 52px -> 32px
            t = self.transition_t
            if t < 0.25:
                # Phase 1: Rapid ease-out expand (0.0 to 0.25) -> size 12 to 52
                u = t / 0.25
                ease = 1.0 - (1.0 - u) ** 2  # quadratic ease-out
                size = constants.SIZE_MUTED + (constants.SIZE_EXPAND_PEAK - constants.SIZE_MUTED) * ease
            else:
                # Phase 2: Smooth settle (0.25 to 1.0) -> size 52 to 32
                u = (t - 0.25) / 0.75
                ease = u * u * (3.0 - 2.0 * u)  # smoothstep
                size = constants.SIZE_EXPAND_PEAK - (constants.SIZE_EXPAND_PEAK - constants.SIZE_UNMUTED) * ease

            self.current_size = size
            self.current_opacity = constants.OPACITY_UNMUTED
        else:
            # 2. Breathing pulse animation (occurs after transition is complete)
            self.pulse_t += dt_ms / constants.PULSE_DURATION_MS
            if self.pulse_t >= 1.0:
                self.pulse_t -= 1.0

            # Slow breathing pulse using a sine wave
            pulse_factor = math.sin(2.0 * math.pi * self.pulse_t)
            self.current_size = constants.SIZE_UNMUTED + constants.PULSE_AMPLITUDE * pulse_factor

            # Pulse opacity slightly with size for dynamic feel
            opacity_factor = 0.85 + 0.15 * pulse_factor
            self.current_opacity = opacity_factor * constants.OPACITY_UNMUTED

        self.update_visuals()
        return True

    def update_visuals(self):
        """Sends repaint signal."""
        self.visuals_updated.emit()
