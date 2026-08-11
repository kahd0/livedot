"""X11/Linux input backend: global hotkey grabs and key forwarding via XTest."""

import threading
import logging
from Xlib import X, XK
from Xlib.display import Display
from Xlib.ext import xtest

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
        return modifiers, mouse_button, True

    # Resolve mapped X11 name if exists
    x11_key_name = QT_TO_X11_KEY_MAP.get(key_name.lower(), key_name)
    return modifiers, x11_key_name, False

def get_keycode_from_keysym(display, keysym_name):
    """Resolves an X11 keysym name to its physical keyboard keycode."""
    keysym = XK.string_to_keysym(keysym_name)
    if keysym == 0:
        # Retry case variants for letters/numbers
        if len(keysym_name) == 1:
            keysym = XK.string_to_keysym(keysym_name.lower())
            if keysym == 0:
                keysym = XK.string_to_keysym(keysym_name.upper())

    if keysym == 0:
        raise ValueError(f"Unknown key keysym: {keysym_name}")

    keycode = display.keysym_to_keycode(keysym)
    if keycode == 0:
        raise ValueError(f"No keycode mapped to keysym: {keysym_name}")

    return keycode

class HotkeyListenerThread(threading.Thread):
    def __init__(self, hotkey_str, trigger_callback):
        super().__init__()
        self.hotkey_str = hotkey_str
        self.callback = trigger_callback
        self.running = True
        self.daemon = True
        self.thread_display = None
        self.error = None  # set when the hotkey could not be installed at all

    def run(self):
        try:
            self.thread_display = Display()
        except Exception as e:
            self.error = f"não foi possível conectar ao servidor X: {e}"
            logger.error(f"Failed to open display connection in hotkey thread: {e}")
            return

        try:
            modifiers, target, is_mouse = parse_hotkey_string(self.hotkey_str)
            if is_mouse:
                button_code = target
                keycode = 0
            else:
                keycode = get_keycode_from_keysym(self.thread_display, target)
                button_code = 0
        except Exception as e:
            self.error = f"atalho '{self.hotkey_str}' inválido: {e}"
            logger.error(f"Failed to parse or map hotkey '{self.hotkey_str}': {e}")
            self.thread_display.close()
            return

        root = self.thread_display.screen().root

        # Grab with different lock masks (NumLock, CapsLock) to avoid active locks blocking hooks
        ignored_locks = [0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask]

        # Ungrab everything first on root to be clean
        try:
            root.ungrab_key(X.AnyKey, X.AnyModifier, root)
        except Exception:
            pass
        try:
            root.ungrab_button(X.AnyButton, X.AnyModifier, root)
        except Exception:
            pass

        if is_mouse:
            logger.info(f"Grabbing global mouse button '{self.hotkey_str}' (button {button_code}, mods {modifiers})")
            for lock in ignored_locks:
                try:
                    root.grab_button(
                        button_code,
                        modifiers | lock,
                        True,
                        X.ButtonPressMask,
                        X.GrabModeAsync,
                        X.GrabModeAsync,
                        X.NONE,
                        X.NONE
                    )
                except Exception as e:
                    logger.error(f"Failed to grab button (mods: {modifiers | lock}, button: {button_code}): {e}")
        else:
            logger.info(f"Grabbing global hotkey '{self.hotkey_str}' (keycode {keycode}, mods {modifiers})")
            for lock in ignored_locks:
                try:
                    root.grab_key(
                        keycode,
                        modifiers | lock,
                        True,
                        X.GrabModeAsync,
                        X.GrabModeAsync
                    )
                except Exception as e:
                    logger.error(f"Failed to grab key combination (mods: {modifiers | lock}, keycode: {keycode}): {e}")

        self.thread_display.sync()

        # Run X11 event loop
        while self.running:
            try:
                event = self.thread_display.next_event()
                if not self.running:
                    break

                if event.type == X.KeyPress and not is_mouse:
                    logger.info("Global keyboard hotkey pressed! Triggering callback...")
                    self.callback()
                elif event.type == X.ButtonPress and is_mouse:
                    if event.detail == button_code:
                        logger.info("Global mouse hotkey pressed! Triggering callback...")
                        self.callback()
            except Exception as e:
                if self.running:
                    logger.error(f"Error in hotkey loop: {e}")
                break

        # Clean up
        try:
            root.ungrab_key(X.AnyKey, X.AnyModifier, root)
            root.ungrab_button(X.AnyButton, X.AnyModifier, root)
            self.thread_display.close()
        except Exception:
            pass
        logger.info("Hotkey listener thread stopped.")

    def stop(self):
        self.running = False
        if self.thread_display:
            try:
                self.thread_display.close()  # Unblocks thread_display.next_event() by raising ConnectionClosed
            except Exception:
                pass

class InputBackend:
    """Holds the long-lived display used for XTest synthesis."""

    def __init__(self):
        self.display = Display()
        self.last_error = None

        # Check XTest extension
        if not self.display.has_extension("XTEST"):
            self.last_error = "extensão XTEST ausente: o encaminhamento do atalho não funciona"
            logger.warning("XTest extension is not supported by this X server! Hotkey forwarding will fail.")

    def create_listener(self, hotkey_str, callback):
        return HotkeyListenerThread(hotkey_str, callback)

    def send_hotkey(self, hotkey_str):
        """Simulates a hotkey globally using the XTest extension."""
        logger.info(f"Simulating hotkey '{hotkey_str}' via XTest...")

        try:
            modifiers, target, is_mouse = parse_hotkey_string(hotkey_str)
            if is_mouse:
                button_code = target
                keycode = 0
            else:
                keycode = get_keycode_from_keysym(self.display, target)
                button_code = 0
        except Exception as e:
            logger.error(f"Failed to parse or resolve hotkey '{hotkey_str}': {e}")
            return

        # Map modifiers to keycodes
        mod_keycodes = []
        try:
            if modifiers & X.ControlMask:
                mod_keycodes.append(get_keycode_from_keysym(self.display, "Control_L"))
            if modifiers & X.Mod1Mask:
                mod_keycodes.append(get_keycode_from_keysym(self.display, "Alt_L"))
            if modifiers & X.ShiftMask:
                mod_keycodes.append(get_keycode_from_keysym(self.display, "Shift_L"))
            if modifiers & X.Mod4Mask:
                mod_keycodes.append(get_keycode_from_keysym(self.display, "Super_L"))
        except Exception as e:
            logger.error(f"Error mapping modifier keycodes for simulation: {e}")
            return

        # Simulate modifier press
        for m_code in mod_keycodes:
            xtest.fake_input(self.display, X.KeyPress, m_code)

        if is_mouse:
            # Simulate mouse button press & release
            xtest.fake_input(self.display, X.ButtonPress, button_code)
            xtest.fake_input(self.display, X.ButtonRelease, button_code)
        else:
            # Simulate keyboard key press & release
            xtest.fake_input(self.display, X.KeyPress, keycode)
            xtest.fake_input(self.display, X.KeyRelease, keycode)

        # Simulate modifier release in reverse order
        for m_code in reversed(mod_keycodes):
            xtest.fake_input(self.display, X.KeyRelease, m_code)

        self.display.sync()
        logger.info("Hotkey simulation complete.")

    def close(self):
        try:
            self.display.close()
        except Exception:
            pass
