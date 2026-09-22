"""X11/Linux input backend: global hotkey grabs on the root window, reporting
both the press and the release."""

import select
import threading
import logging
from Xlib import X, XK, error as Xerror
from Xlib.display import Display

logger = logging.getLogger("livedot.input")

# Map of common Qt key names to X11 Keysym names
QT_TO_X11_KEY_MAP = {
    "space": "space",
    "return": "Return",
    "enter": "Return",
    "escape": "Escape",
    "backspace": "BackSpace",
    "tab": "Tab",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "delete": "Delete",
    "insert": "Insert",
    "home": "Home",
    "end": "End",
    "pageup": "Prior",
    "page up": "Prior",
    "pagedown": "Next",
    "page down": "Next",
    "capslock": "Caps_Lock",
    "caps lock": "Caps_Lock",
    "numlock": "Num_Lock",
    "num lock": "Num_Lock",
    "scrolllock": "Scroll_Lock",
    "scroll lock": "Scroll_Lock"
}

# Grab once per lock-key combination so an active NumLock/CapsLock doesn't
# stop the hotkey from matching.
IGNORED_LOCKS = (0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask)

# X autorepeat turns a held key into KeyRelease/KeyPress pairs. The server
# stamps both halves of a pair separately, so they can be a millisecond apart;
# no human releases and presses a key again this fast.
AUTOREPEAT_WINDOW_MS = 20

# A KeyRelease only counts once no autorepeat KeyPress has followed it for
# this long. Both halves are sent together, so this is plenty.
RELEASE_CONFIRM_S = 0.03

# Backoff ceiling when the X connection drops and has to be reopened.
RECONNECT_MAX_S = 30

# How often the event loop wakes up to check whether stop() was called.
POLL_INTERVAL_S = 0.25


def parse_hotkey_string(hotkey_str):
    """
    Parses a hotkey string (e.g. 'Ctrl+Alt+M' or 'Ctrl+Mouse8') into X11 modifier masks,
    the target keysym/button_code, and a boolean is_mouse flag.
    """
    parts = hotkey_str.split("+")
    modifiers = 0
    key_name = ""
    is_mouse = False
    mouse_button = 0

    for part in parts:
        p_clean = part.strip().lower()
        if p_clean in ("ctrl", "control"):
            modifiers |= X.ControlMask
        elif p_clean in ("alt", "mod1"):
            modifiers |= X.Mod1Mask
        elif p_clean == "shift":
            modifiers |= X.ShiftMask
        elif p_clean in ("super", "win", "meta", "mod4"):
            modifiers |= X.Mod4Mask
        elif p_clean.startswith("mouse"):
            is_mouse = True
            try:
                # e.g. "mouse8" -> 8
                mouse_button = int(p_clean[5:])
            except ValueError:
                mouse_button = 0
        else:
            key_name = part.strip()

    if is_mouse:
        if mouse_button <= 0:
            raise ValueError(f"Unknown mouse button in '{hotkey_str}'")
        return modifiers, mouse_button, True

    # Resolve mapped X11 name if exists
    x11_key_name = QT_TO_X11_KEY_MAP.get(key_name.lower(), key_name)
    return modifiers, x11_key_name, False


def get_keycode_from_keysym(display, keysym_name):
    """Resolves an X11 keysym name to its physical keyboard keycode."""
    keysym = XK.string_to_keysym(keysym_name)
    if keysym == 0 and len(keysym_name) == 1:
        # Retry case variants for letters, then the character itself:
        # Latin-1 keysyms equal their code point, which covers punctuation
        # such as "," whose keysym is named "comma".
        keysym = (XK.string_to_keysym(keysym_name.lower())
                  or XK.string_to_keysym(keysym_name.upper())
                  or (ord(keysym_name) if ord(keysym_name) < 0x100 else 0))

    if keysym == 0:
        raise ValueError(f"Unknown key keysym: {keysym_name}")

    keycode = display.keysym_to_keycode(keysym)
    if keycode == 0:
        raise ValueError(f"No keycode mapped to keysym: {keysym_name}")

    return keycode


class HotkeyListenerThread(threading.Thread):
    """Grabs the hotkey on the root window and calls back on every press and
    release.

    Reconnects on its own if the X connection drops, so the hotkey doesn't
    silently die for the rest of the session.
    """

    def __init__(self, hotkey_str, on_press, on_release):
        super().__init__(daemon=True)
        self.hotkey_str = hotkey_str
        self.on_press = on_press
        self.on_release = on_release
        self.error = None  # human-readable reason the hotkey isn't working
        self.display = None
        self._stop_event = threading.Event()
        self._is_mouse = False
        self._keycode = 0
        self._button = 0
        self._held = False
        self._pending_release = None  # server time of a KeyRelease not yet confirmed

    def run(self):
        delay = 1
        while not self._stop_event.is_set():
            if not self._listen_once():
                break
            if self._stop_event.wait(delay):
                break
            delay = min(delay * 2, RECONNECT_MAX_S)
        logger.info("Hotkey listener thread stopped.")

    def _listen_once(self):
        """Grabs the hotkey and dispatches events until the connection ends.
        Returns True when reconnecting is worth a try."""
        try:
            display = Display()
        except Exception as e:
            self.error = f"não foi possível conectar ao servidor X: {e}"
            logger.error(f"Failed to open display connection in hotkey thread: {e}")
            return True

        self.display = display
        try:
            if self._stop_event.is_set() or not self._grab(display):
                return False
            self.error = None
            self._held = False
            self._pending_release = None
            while not self._stop_event.is_set():
                # Drain what is queued, then wait on the socket with a timeout
                # so stop() is noticed. Closing the display from another
                # thread would not wake a blocked next_event().
                while display.pending_events():
                    self._handle_event(display.next_event())
                waiting = self._pending_release is not None
                readable, _, _ = select.select([display], [], [],
                                               RELEASE_CONFIRM_S if waiting else POLL_INTERVAL_S)
                if waiting and not readable:
                    self._pending_release = None
                    self._release()
            return False
        except Exception as e:
            if self._stop_event.is_set():
                return False
            self.error = "conexão com o servidor X perdida; reconectando"
            logger.error(f"Error in hotkey loop: {e}. Reconnecting...")
            return True
        finally:
            self.display = None
            try:
                # Closing the connection also releases every grab it holds.
                display.close()
            except Exception:
                pass

    def _grab(self, display):
        try:
            modifiers, target, self._is_mouse = parse_hotkey_string(self.hotkey_str)
            if self._is_mouse:
                self._button = target
            else:
                self._keycode = get_keycode_from_keysym(display, target)
        except Exception as e:
            self.error = f"atalho '{self.hotkey_str}' inválido: {e}"
            logger.error(f"Failed to parse or map hotkey '{self.hotkey_str}': {e}")
            return False

        root = display.screen().root
        # Grab errors come back asynchronously, so a try/except around the
        # calls never sees them. Collect them and check after a round trip.
        catcher = Xerror.CatchError(Xerror.BadAccess)
        for lock in IGNORED_LOCKS:
            if self._is_mouse:
                root.grab_button(self._button, modifiers | lock, True,
                                 X.ButtonPressMask | X.ButtonReleaseMask,
                                 X.GrabModeAsync, X.GrabModeAsync,
                                 X.NONE, X.NONE, onerror=catcher)
            else:
                root.grab_key(self._keycode, modifiers | lock, True,
                              X.GrabModeAsync, X.GrabModeAsync, onerror=catcher)
        display.sync()

        if catcher.get_error():
            self.error = f"o atalho '{self.hotkey_str}' já é usado por outro programa"
            logger.error(f"Hotkey '{self.hotkey_str}' is already grabbed by another client (BadAccess).")
            return False

        what = f"button {self._button}" if self._is_mouse else f"keycode {self._keycode}"
        logger.info(f"Grabbed global hotkey '{self.hotkey_str}' ({what}, mods {modifiers})")
        return True

    def _handle_event(self, event):
        if self._is_mouse:
            if event.type == X.ButtonPress and event.detail == self._button:
                self._press()
            elif event.type == X.ButtonRelease and event.detail == self._button:
                self._release()
        elif event.type == X.KeyRelease and event.detail == self._keycode:
            self._pending_release = event.time  # confirmed by the event loop
        elif event.type == X.KeyPress and event.detail == self._keycode:
            if (self._pending_release is not None
                    and (event.time - self._pending_release) & 0xFFFFFFFF <= AUTOREPEAT_WINDOW_MS):
                self._pending_release = None
                return  # autorepeat while the key is held down
            if self._pending_release is not None:
                self._pending_release = None
                self._release()
            self._press()

    def _press(self):
        if not self._held:
            self._held = True
            logger.info("Global hotkey pressed! Triggering callback...")
            self.on_press()

    def _release(self):
        if self._held:
            self._held = False
            self.on_release()

    def stop(self):
        self._stop_event.set()
        # Wait for the grabs to be released, so a new listener can take over
        # the same combination right away.
        if self.is_alive() and threading.current_thread() is not self:
            self.join(timeout=1.0)
