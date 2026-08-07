import os
import sys

# Application Identifiers
APP_NAME = "livedot"
SINGLE_INSTANCE_KEY = "LivedotSingleInstanceLock"

# Paths
if sys.platform == "win32":
    # %APPDATA% is the Windows counterpart of ~/.config
    _CONFIG_ROOT = os.environ.get("APPDATA") or os.path.expanduser("~")
    CONFIG_DIR = os.path.join(_CONFIG_ROOT, "Livedot")
else:
    CONFIG_DIR = os.path.expanduser(f"~/.config/{APP_NAME}")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
LOG_DIR = os.path.join(CONFIG_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "livedot.log")
SOUND_DIR = os.path.join(CONFIG_DIR, "sounds")

MUTE_SOUND_FILE = os.path.join(SOUND_DIR, "mute.wav")
UNMUTE_SOUND_FILE = os.path.join(SOUND_DIR, "unmute.wav")

# Visual Styling - Colors (RGB)
COLOR_MUTED = (30, 41, 59)       # Dark Blue (Slate-800)
COLOR_UNMUTED = (239, 68, 68)    # Vibrant Red (Red-500)
COLOR_BORDER = (255, 255, 255)   # White border / glow hint

# Visual Styling - Opacities
OPACITY_MUTED = 0.4
OPACITY_UNMUTED = 0.9

# Visual Styling - Sizes (Diameter in Pixels)
SIZE_MUTED = 12
SIZE_UNMUTED = 32
SIZE_EXPAND_PEAK = 52

# Animation Timings
TRANSITION_DURATION_MS = 1000   # 1 second auto-expand transition
PULSE_DURATION_MS = 2400        # Breathing pulse cycle length
PULSE_AMPLITUDE = 3             # Radius breathing scale variance (px)
FPS = 60                        # Framerate for transitions

# Interaction Settings
DRAG_THRESHOLD_MS = 300         # Hold mouse for 300ms to start dragging
DRAG_THRESHOLD_PX = 5           # Move mouse at least 5px to confirm drag
SAVE_DEBOUNCE_MS = 500          # Debounce write to disk after drag/resize

# Default Configurations
DEFAULT_APP_HOTKEY = "Ctrl+Alt+M"
DEFAULT_DISCORD_HOTKEY = "Ctrl+Shift+F12"
DEFAULT_SOUND_ENABLED = True
DEFAULT_AUTOSTART_ENABLED = False
DEFAULT_SCALE = 1.0             # Scale multiplier
DEFAULT_POSITION_LOCKED = False
