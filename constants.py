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
COLOR_IDLE = (100, 116, 139)        # Slate-500, the speck shown outside a voice channel
COLOR_MESSAGE = (88, 101, 242)      # Discord blurple, the unread-message badge

# Visual Styling - Opacities
OPACITY_MUTED = 0.4
OPACITY_UNMUTED = 0.9
OPACITY_DISCONNECTED = 0.7
OPACITY_IDLE = 0.35

# Visual Styling - Sizes (Diameter in Pixels)
SIZE_MUTED = 12
SIZE_UNMUTED = 32
SIZE_EXPAND_PEAK = 52
SIZE_IDLE = 6
DEAF_RING_GAP = 3               # Space between the dot and the deafened ring
SIZE_BADGE = 9                  # Unread-message badge
BADGE_OFFSET = 5                # Badge center beyond the dot's resting edge
BADGE_HIT_SLOP = 4              # Extra radius that still counts as clicking the badge
WINDOW_SIZE = 80                # Bounding box of the overlay at scale 1.0

# Animation Timings
TRANSITION_DURATION_MS = 1000   # 1 second auto-expand transition
PULSE_DURATION_MS = 2400        # Breathing pulse cycle length
PULSE_AMPLITUDE = 3             # Radius breathing scale variance (px)
FPS = 30                        # Framerate for transitions
FLASH_PERIOD_MS = 500           # One on/off cycle of the amber ring
FLASH_BLINKS = 3                # Launched again, or a forgotten mic was muted
JOIN_FLASH_BLINKS = 1           # Just joined a voice channel
BADGE_POP_MS = 450              # Badge appearing or reminding
BADGE_POP_PEAK = 1.4            # Badge scale at the top of the pop
MESSAGE_REMIND_AFTER_MS = 15 * 60_000   # Unread this long: pop again...
MESSAGE_REMIND_EVERY_MS = 5 * 60_000    # ...and then every so often
FOCUS_POLL_MS = 500             # Checks for Discord in front while the badge is up

# Interaction Settings
DRAG_THRESHOLD_MS = 300         # Hold mouse for 300ms to start dragging
DRAG_THRESHOLD_PX = 5           # Move mouse at least 5px to confirm drag
SAVE_DEBOUNCE_MS = 500          # Debounce write to disk after drag/resize
HOLD_THRESHOLD_MS = 400         # Hotkey held this long only flips the mic while held

# Discord
DISCORD_RECONNECT_MS = 5000     # Retry interval while Discord is closed

# Default Configurations
DEFAULT_APP_HOTKEY = "Ctrl+Alt+M"
DEFAULT_AUTOSTART_ENABLED = False
DEFAULT_SCALE = 1.0             # Scale multiplier
DEFAULT_OPACITY = 1.0           # Opacity multiplier
DEFAULT_POSITION_LOCKED = False
DEFAULT_JOIN_MUTED = True
DEFAULT_IDLE_MUTE_MINUTES = 5   # Mute an open mic after this long in silence; 0 = never
