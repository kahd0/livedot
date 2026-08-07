import os
import sys
import logging

logger = logging.getLogger("livedot.autostart")

IS_WINDOWS = sys.platform == "win32"

# Linux: XDG autostart entry
AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
AUTOSTART_FILE = os.path.join(AUTOSTART_DIR, "livedot.desktop")

# Windows: per-user Run key
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "Livedot"

if IS_WINDOWS:
    import winreg


def _launch_command() -> str:
    """Builds the command line that starts Livedot, quoted for the shell."""
    # A PyInstaller build is its own launcher; sys.executable is the .exe.
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'

    current_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(current_dir, "livedot.py")
    python_exe = sys.executable

    if IS_WINDOWS:
        # pythonw.exe runs without opening a console window.
        pythonw = os.path.join(os.path.dirname(python_exe), "pythonw.exe")
        if os.path.exists(pythonw):
            python_exe = pythonw
    elif "venv" not in python_exe:
        candidate = os.path.join(current_dir, "venv", "bin", "python3")
        if os.path.exists(candidate):
            python_exe = candidate

    return f'"{python_exe}" "{script_path}"'


def _set_autostart_windows(enabled: bool) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, _launch_command())
                logger.info(f"Autostart enabled. Wrote HKCU\\{RUN_KEY}\\{RUN_VALUE_NAME}")
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE_NAME)
                    logger.info(f"Autostart disabled. Removed HKCU\\{RUN_KEY}\\{RUN_VALUE_NAME}")
                except FileNotFoundError:
                    pass  # already absent
        return True
    except Exception as e:
        logger.error(f"Failed to update autostart registry value: {e}")
        return False


def _set_autostart_linux(enabled: bool) -> bool:
    if not os.path.exists(AUTOSTART_DIR):
        try:
            os.makedirs(AUTOSTART_DIR, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create autostart directory: {e}")
            return False

    if enabled:
        desktop_content = f"""[Desktop Entry]
Type=Application
Name=Livedot
Comment=Minimalist Discord microphone status overlay
Exec={_launch_command()}
Icon=audio-input-microphone
Terminal=false
Categories=Utility;
X-GNOME-Autostart-enabled=true
"""
        try:
            with open(AUTOSTART_FILE, "w") as f:
                f.write(desktop_content)
            # Mark the desktop entry as executable
            os.chmod(AUTOSTART_FILE, 0o755)
            logger.info(f"Autostart enabled. Created .desktop shortcut at {AUTOSTART_FILE}")
            return True
        except Exception as e:
            logger.error(f"Failed to write autostart desktop entry: {e}")
            return False
    else:
        if os.path.exists(AUTOSTART_FILE):
            try:
                os.remove(AUTOSTART_FILE)
                logger.info(f"Autostart disabled. Removed .desktop entry at {AUTOSTART_FILE}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete autostart entry: {e}")
                return False
        return True


def set_autostart(enabled: bool) -> bool:
    """Enables or disables launching Livedot when the user session starts."""
    if IS_WINDOWS:
        return _set_autostart_windows(enabled)
    return _set_autostart_linux(enabled)


def is_autostart_enabled() -> bool:
    """Checks whether the autostart entry is currently registered."""
    if IS_WINDOWS:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                                winreg.KEY_QUERY_VALUE) as key:
                winreg.QueryValueEx(key, RUN_VALUE_NAME)
                return True
        except FileNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Failed to read autostart registry value: {e}")
            return False
    return os.path.exists(AUTOSTART_FILE)
