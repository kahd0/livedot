import os
import sys

# Application Identifiers
APP_NAME = "livedot"
SINGLE_INSTANCE_KEY = "LivedotSingleInstanceLock"
INSTANCE_SERVER_NAME = "livedot-instance"  # local socket; launching again connects to it

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
LOG_MAX_BYTES = 512 * 1024      # Rotate the log past this size, keeping one backup

# Visual Styling - Colors (RGB)
COLOR_MUTED = (30, 41, 59)          # Dark Blue (Slate-800)
COLOR_UNMUTED = (239, 68, 68)       # Vibrant Red (Red-500)
COLOR_DISCONNECTED = (148, 163, 184)  # Gray (Slate-400), drawn as a hollow ring
COLOR_BORDER = (255, 255, 255)      # White border / glow hint
COLOR_FLASH = (251, 191, 36)        # Amber (Amber-400) ring blinked to find the dot

# Visual Styling - Opacities
OPACITY_MUTED = 0.4
OPACITY_UNMUTED = 0.9
OPACITY_DISCONNECTED = 0.7

# Visual Styling - Sizes (Diameter in Pixels)
SIZE_MUTED = 12
SIZE_UNMUTED = 32
SIZE_EXPAND_PEAK = 52
WINDOW_SIZE = 80                # Bounding box of the overlay at scale 1.0

# Animation Timings
TRANSITION_DURATION_MS = 1000   # 1 second auto-expand transition
PULSE_DURATION_MS = 2400        # Breathing pulse cycle length
PULSE_AMPLITUDE = 3             # Radius breathing scale variance (px)
FPS = 30                        # Framerate for transitions
FLASH_DURATION_MS = 1500        # Blinking when the app is launched again
FLASH_BLINKS = 3

# Interaction Settings
DRAG_THRESHOLD_MS = 300         # Hold mouse for 300ms to start dragging
DRAG_THRESHOLD_PX = 5           # Move mouse at least 5px to confirm drag
SAVE_DEBOUNCE_MS = 500          # Debounce write to disk after drag/resize

# Discord
DISCORD_RECONNECT_MS = 5000     # Retry interval while Discord is closed

# Default Configurations
DEFAULT_APP_HOTKEY = "Ctrl+Alt+M"
DEFAULT_AUTOSTART_ENABLED = False
DEFAULT_SCALE = 1.0             # Scale multiplier
DEFAULT_OPACITY = 1.0           # Opacity multiplier
DEFAULT_POSITION_LOCKED = False
