import os
import json
import math
import logging
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QDateTime, QPoint

import constants

logger = logging.getLogger("livedot.state")

class StateManager(QObject):
    # Signals to notify the UI
    state_changed = pyqtSignal(bool)       # Emits: is_muted
    visuals_updated = pyqtSignal()          # Emits whenever size/color/opacity changes
    config_saved = pyqtSignal()             # Emits when config is saved

    def __init__(self):
        super().__init__()
        
        # Core Runtime States
        self.muted = True
        self.current_size = constants.SIZE_MUTED
        self.current_opacity = constants.OPACITY_MUTED
        self.current_color = constants.COLOR_MUTED
        
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
        
        # Logging setup
        os.makedirs(constants.LOG_DIR, exist_ok=True)
        logging.basicConfig(
            filename=constants.LOG_FILE,
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        logger.info("StateManager initialized.")

    def load_config(self):
        """Loads configuration from JSON file. Falls back to defaults if not found."""
        try:
            if os.path.exists(constants.CONFIG_FILE):
                with open(constants.CONFIG_FILE, "r") as f:
                    self.config = json.load(f)
                logger.info(f"Configuration loaded from {constants.CONFIG_FILE}")
            else:
                logger.info("Configuration file not found. Initializing defaults.")
                self.config = {}
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self.config = {}

        # Set defaults for missing keys
        self.config.setdefault("position_x", 100)
        self.config.setdefault("position_y", 700)
        self.config.setdefault("scale", constants.DEFAULT_SCALE)
        self.config.setdefault("opacity", constants.OPACITY_UNMUTED)
        self.config.setdefault("app_hotkey", constants.DEFAULT_APP_HOTKEY)
        self.config.setdefault("discord_hotkey", constants.DEFAULT_DISCORD_HOTKEY)
        self.config.setdefault("sound_enabled", constants.DEFAULT_SOUND_ENABLED)
        self.config.setdefault("autostart_enabled", constants.DEFAULT_AUTOSTART_ENABLED)
        self.config.setdefault("position_locked", constants.DEFAULT_POSITION_LOCKED)

    def save_config(self):
        """Directly writes the configuration dictionary to JSON file."""
        try:
            os.makedirs(constants.CONFIG_DIR, exist_ok=True)
            with open(constants.CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=4)
            logger.info(f"Configuration saved to {constants.CONFIG_FILE}")
            self.config_saved.emit()
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")

    def save_config_debounced(self):
        """Schedules a config save, debouncing continuous events like window drags."""
        self.save_timer.start(constants.SAVE_DEBOUNCE_MS)

    # State modification APIs
    def set_muted(self, muted, trigger_sounds=True):
        if self.muted == muted:
            return
            
        self.muted = muted
        logger.info(f"Microphone state changed: Muted = {self.muted}")
        
        # Reset transition timers
        if not self.muted:
            # Trigger rapid auto-expand when unmuting
            self.transition_t = 0.0
            self.pulse_t = 0.0
            # Initialize visually to starting state (12px unmuted, red)
            self.current_size = constants.SIZE_MUTED
            self.current_opacity = constants.OPACITY_UNMUTED * self.config["opacity"]
            self.current_color = constants.COLOR_UNMUTED
        else:
            # Immediate transition when muting (calma visual)
            self.transition_t = 1.0
            self.pulse_t = 0.0
            # Immediately update values to muted constants!
            self.current_size = constants.SIZE_MUTED
            self.current_opacity = constants.OPACITY_MUTED * self.config["opacity"]
            self.current_color = constants.COLOR_MUTED
            
        self.update_visuals()
        self.state_changed.emit(self.muted)

    def toggle_mute(self, trigger_sounds=True):
        self.set_muted(not self.muted, trigger_sounds)

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

    def set_discord_hotkey(self, hotkey):
        self.config["discord_hotkey"] = hotkey
        self.save_config_debounced()

    def set_sound_enabled(self, enabled):
        self.config["sound_enabled"] = enabled
        self.save_config_debounced()

    def set_autostart_enabled(self, enabled):
        self.config["autostart_enabled"] = enabled
        self.save_config_debounced()

    # Drag / Click Handler Methods
    def handle_mouse_press(self, global_pos: QPoint):
        self.press_time = QDateTime.currentMSecsSinceEpoch()
        self.press_pos = global_pos
        self.drag_started = False

    def handle_mouse_move(self, global_pos: QPoint):
        if self.config["position_locked"]:
            return False
            
        if not self.drag_started:
            time_elapsed = QDateTime.currentMSecsSinceEpoch() - self.press_time
            delta = global_pos - self.press_pos
            distance = math.sqrt(delta.x()**2 + delta.y()**2)
            
            if time_elapsed >= constants.DRAG_THRESHOLD_MS and distance >= constants.DRAG_THRESHOLD_PX:
                self.drag_started = True
                return True
            return False
        return True

    def handle_mouse_release(self, global_pos: QPoint):
        if not self.drag_started:
            # Clean single click -> toggle mute
            self.toggle_mute()
            return True
        self.drag_started = False
        return False

    # Animation update calculations
    def advance_time(self, dt_ms):
        """Advances the internal timers and updates current visuals based on progress."""
        need_repaint = False

        if self.muted:
            # Under muted state, values are static
            self.current_size = constants.SIZE_MUTED
            self.current_opacity = constants.OPACITY_MUTED * self.config["opacity"]
            self.current_color = constants.COLOR_MUTED
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
            self.current_opacity = constants.OPACITY_UNMUTED * self.config["opacity"]
            self.current_color = constants.COLOR_UNMUTED
            need_repaint = True
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
            self.current_opacity = opacity_factor * constants.OPACITY_UNMUTED * self.config["opacity"]
            self.current_color = constants.COLOR_UNMUTED
            need_repaint = True
            
        self.update_visuals()
        return need_repaint

    def update_visuals(self):
        """Sends repaint signal."""
        self.visuals_updated.emit()
