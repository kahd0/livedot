"""Windows input backend: global hotkeys via RegisterHotKey / WH_MOUSE_LL,
key forwarding via SendInput. Mirrors the semantics of input_x11.py."""

import ctypes
import ctypes.wintypes as wintypes
import threading
import logging

logger = logging.getLogger("livedot.input")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# RegisterHotKey modifier flags
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

WM_QUIT = 0x0012
WM_HOTKEY = 0x0312
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C

WH_MOUSE_LL = 14
HC_ACTION = 0

XBUTTON1 = 0x0001  # "Back" thumb button  -> X11 button 8
XBUTTON2 = 0x0002  # "Forward" thumb button -> X11 button 9

# Virtual-key codes needed for modifier synthesis
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_LWIN = 0x5B

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_XDOWN = 0x0080
MOUSEEVENTF_XUP = 0x0100

HOTKEY_ID = 1

# Stamped into dwExtraInfo of every event we synthesize so our own low-level
# mouse hook can tell them apart from real clicks. Without this, binding the
# app hotkey and the Discord hotkey to the same mouse button would make the
# forwarded click re-trigger the toggle in a loop.
INJECTED_SIGNATURE = 0x4C564454  # "LVDT"

# Qt key names -> virtual-key codes. Single characters and F-keys are resolved
# dynamically below, so only the named keys need to live here.
VK_MAP = {
    "space": 0x20,
    "return": 0x0D,
    "enter": 0x0D,
    "escape": 0x1B,
    "backspace": 0x08,
    "tab": 0x09,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "delete": 0x2E,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "page up": 0x21,
    "pagedown": 0x22,
    "page down": 0x22,
    "capslock": 0x14,
    "caps lock": 0x14,
    "numlock": 0x90,
    "num lock": 0x90,
    "scrolllock": 0x91,
    "scroll lock": 0x91,
    "print": 0x2C,
    "pause": 0x13,
}
for _i in range(1, 25):
    VK_MAP[f"f{_i}"] = 0x6F + _i  # VK_F1 == 0x70

# Keys that live on the extended half of the keyboard; SendInput needs the flag
# or the receiving app sees the numpad twin instead.
EXTENDED_VKS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
                0x2C, 0x2D, 0x2E, 0x90, 0x6F, 0xA3, 0xA5}

ULONG_PTR = ctypes.c_uint64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
LRESULT = ctypes.c_ssize_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wintypes.POINT),
                ("mouseData", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
user32.RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
user32.GetMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.VkKeyScanW.argtypes = (wintypes.WCHAR,)
user32.VkKeyScanW.restype = ctypes.c_short
kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE


def parse_hotkey_string(hotkey_str):
    """
    Parses a hotkey string (e.g. 'Ctrl+Alt+M' or 'Ctrl+Mouse8') into RegisterHotKey
    modifier flags, the target virtual-key code / XBUTTON code, and an is_mouse flag.
    """
    parts = hotkey_str.split("+")
    modifiers = 0
    key_name = ""
    is_mouse = False
    mouse_button = 0

    for part in parts:
        p_clean = part.strip().lower()
        if p_clean in ("ctrl", "control"):
            modifiers |= MOD_CONTROL
        elif p_clean in ("alt", "mod1"):
            modifiers |= MOD_ALT
        elif p_clean == "shift":
            modifiers |= MOD_SHIFT
        elif p_clean in ("super", "win", "meta", "mod4"):
            modifiers |= MOD_WIN
        elif p_clean.startswith("mouse"):
            is_mouse = True
            try:
                mouse_button = int(p_clean[5:])
            except ValueError:
                mouse_button = 0
        else:
            key_name = part.strip()

    if is_mouse:
        # The dialog records X11-style numbering: 8 = Back, 9 = Forward,
        # 10 = Task (no Windows equivalent).
        if mouse_button == 8:
            return modifiers, XBUTTON1, True
        if mouse_button == 9:
            return modifiers, XBUTTON2, True
        raise ValueError(f"Mouse button {mouse_button} has no Windows equivalent")

    return modifiers, get_vk_from_name(key_name), False


def get_vk_from_name(key_name):
    """Resolves a Qt-style key name to a Windows virtual-key code."""
    if not key_name:
        raise ValueError("Empty key name")

    mapped = VK_MAP.get(key_name.lower())
    if mapped is not None:
        return mapped

    if len(key_name) == 1:
        char = key_name.upper()
        # Letters and digits map straight onto their ASCII value.
        if char.isalnum() and char.isascii():
            return ord(char)
        # Punctuation depends on the active layout.
        scan = user32.VkKeyScanW(key_name)
        if scan != -1:
            return scan & 0xFF

    raise ValueError(f"Unknown key name: {key_name}")


def _key_input(vk, keyup):
    flags = KEYEVENTF_KEYUP if keyup else 0
    if vk in EXTENDED_VKS:
        flags |= KEYEVENTF_EXTENDEDKEY
    item = INPUT(type=INPUT_KEYBOARD)
    item.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0,
                         dwExtraInfo=INJECTED_SIGNATURE)
    return item


def _xbutton_input(xbutton, keyup):
    item = INPUT(type=INPUT_MOUSE)
    item.mi = MOUSEINPUT(dx=0, dy=0, mouseData=xbutton,
                         dwFlags=MOUSEEVENTF_XUP if keyup else MOUSEEVENTF_XDOWN,
                         time=0, dwExtraInfo=INJECTED_SIGNATURE)
    return item


class HotkeyListenerThread(threading.Thread):
    """Owns a Win32 message loop. Keyboard hotkeys go through RegisterHotKey;
    thumb-button hotkeys need a low-level mouse hook, which RegisterHotKey
    cannot express."""

    def __init__(self, hotkey_str, trigger_callback):
        super().__init__()
        self.hotkey_str = hotkey_str
        self.callback = trigger_callback
        self.running = True
        self.daemon = True
        self._thread_id = None
        self._started = threading.Event()
        self._modifiers = 0
        self._target = 0
        self._hook_ref = None  # must outlive the hook or Windows calls into freed memory

    def run(self):
        self._thread_id = kernel32.GetCurrentThreadId()
        self._started.set()

        try:
            self._modifiers, self._target, is_mouse = parse_hotkey_string(self.hotkey_str)
        except Exception as e:
            logger.error(f"Failed to parse or map hotkey '{self.hotkey_str}': {e}")
            return

        hook = None
        registered = False

        if is_mouse:
            logger.info(f"Hooking global mouse button '{self.hotkey_str}' (xbutton {self._target}, mods {self._modifiers})")
            self._hook_ref = HOOKPROC(self._on_mouse_event)
            hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._hook_ref,
                                            kernel32.GetModuleHandleW(None), 0)
            if not hook:
                logger.error(f"Failed to install mouse hook: error {ctypes.get_last_error()}")
                return
        else:
            logger.info(f"Registering global hotkey '{self.hotkey_str}' (vk {self._target}, mods {self._modifiers})")
            registered = bool(user32.RegisterHotKey(None, HOTKEY_ID,
                                                    self._modifiers | MOD_NOREPEAT,
                                                    self._target))
            if not registered:
                # Most commonly means another application already owns the combo.
                logger.error(f"Failed to register hotkey '{self.hotkey_str}': error {ctypes.get_last_error()}")
                return

        msg = wintypes.MSG()
        while self.running:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret in (0, -1):  # WM_QUIT or error
                break
            if msg.message == WM_HOTKEY:
                logger.info("Global keyboard hotkey pressed! Triggering callback...")
                self.callback()
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if hook:
            user32.UnhookWindowsHookEx(hook)
        if registered:
            user32.UnregisterHotKey(None, HOTKEY_ID)
        logger.info("Hotkey listener thread stopped.")

    def _on_mouse_event(self, n_code, w_param, l_param):
        if n_code == HC_ACTION and w_param in (WM_XBUTTONDOWN, WM_XBUTTONUP):
            info = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            xbutton = (info.mouseData >> 16) & 0xFFFF
            if (info.dwExtraInfo != INJECTED_SIGNATURE
                    and xbutton == self._target
                    and self._modifiers_held()):
                if w_param == WM_XBUTTONDOWN:
                    logger.info("Global mouse hotkey pressed! Triggering callback...")
                    self.callback()
                # Swallow both halves of the click to match the X11 grab, which
                # keeps the button from also reaching the focused window.
                return 1
        return user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _modifiers_held(self):
        def down(vk):
            return bool(user32.GetAsyncKeyState(vk) & 0x8000)

        if bool(self._modifiers & MOD_CONTROL) != down(VK_CONTROL):
            return False
        if bool(self._modifiers & MOD_ALT) != down(VK_MENU):
            return False
        if bool(self._modifiers & MOD_SHIFT) != down(VK_SHIFT):
            return False
        return True

    def stop(self):
        self.running = False
        # Wait for run() to publish its thread id, otherwise the WM_QUIT is
        # posted nowhere and GetMessageW blocks forever.
        self._started.wait(timeout=2.0)
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)


class InputBackend:
    def __init__(self):
        # SendInput is stateless, so there is no display handle to keep here.
        pass

    def create_listener(self, hotkey_str, callback):
        return HotkeyListenerThread(hotkey_str, callback)

    def send_hotkey(self, hotkey_str):
        """Simulates a hotkey globally using SendInput."""
        logger.info(f"Simulating hotkey '{hotkey_str}' via SendInput...")

        try:
            modifiers, target, is_mouse = parse_hotkey_string(hotkey_str)
        except Exception as e:
            logger.error(f"Failed to parse or resolve hotkey '{hotkey_str}': {e}")
            return

        mod_vks = []
        if modifiers & MOD_CONTROL:
            mod_vks.append(VK_CONTROL)
        if modifiers & MOD_ALT:
            mod_vks.append(VK_MENU)
        if modifiers & MOD_SHIFT:
            mod_vks.append(VK_SHIFT)
        if modifiers & MOD_WIN:
            mod_vks.append(VK_LWIN)

        events = [_key_input(vk, keyup=False) for vk in mod_vks]

        if is_mouse:
            events.append(_xbutton_input(target, keyup=False))
            events.append(_xbutton_input(target, keyup=True))
        else:
            events.append(_key_input(target, keyup=False))
            events.append(_key_input(target, keyup=True))

        events.extend(_key_input(vk, keyup=True) for vk in reversed(mod_vks))

        array = (INPUT * len(events))(*events)
        sent = user32.SendInput(len(events), array, ctypes.sizeof(INPUT))
        if sent != len(events):
            # Blocked input, or the foreground app runs at a higher integrity
            # level than we do (UIPI).
            logger.error(f"SendInput delivered {sent}/{len(events)} events: error {ctypes.get_last_error()}")
            return

        logger.info("Hotkey simulation complete.")

    def close(self):
        pass
