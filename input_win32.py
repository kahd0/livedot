"""Windows input backend: global hotkeys via RegisterHotKey (falling back to a
WH_KEYBOARD_LL hook) plus WH_MOUSE_LL for thumb buttons, key forwarding via
SendInput. Mirrors the semantics of input_x11.py."""

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
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
HC_ACTION = 0

ERROR_HOTKEY_ALREADY_REGISTERED = 1409

XBUTTON1 = 0x0001  # "Back" thumb button  -> X11 button 8
XBUTTON2 = 0x0002  # "Forward" thumb button -> X11 button 9

# Generic modifier virtual-keys: what GetAsyncKeyState and RegisterHotKey speak.
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_LWIN = 0x5B
VK_RWIN = 0x5C

# Sided variants. SendInput has to use these: a real keyboard never emits the
# generic VK_CONTROL, and apps that key off the sided code (or the scan code
# behind it) ignore the generic one.
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4
VK_RMENU = 0xA5

# (RegisterHotKey flag, generic VK, VK to synthesize) for every modifier.
MODIFIERS = (
    (MOD_CONTROL, VK_CONTROL, VK_LCONTROL, (VK_LCONTROL, VK_RCONTROL)),
    (MOD_ALT, VK_MENU, VK_LMENU, (VK_LMENU, VK_RMENU)),
    (MOD_SHIFT, VK_SHIFT, VK_LSHIFT, (VK_LSHIFT, VK_RSHIFT)),
    (MOD_WIN, VK_LWIN, VK_LWIN, (VK_LWIN, VK_RWIN)),
)

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_XDOWN = 0x0080
MOUSEEVENTF_XUP = 0x0100

MAPVK_VK_TO_VSC_EX = 4

HOTKEY_ID = 1

# Stamped into dwExtraInfo of every event we synthesize so our own low-level
# hooks can tell them apart from real input. Without this, binding the app
# hotkey and the Discord hotkey to the same key or button would make the
# forwarded event re-trigger the toggle in a loop.
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

# Keys that live on the extended half of the keyboard. MapVirtualKeyW normally
# reports these itself; the set is a backstop for layouts where it doesn't.
EXTENDED_VKS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
                0x2C, 0x2D, 0x2E, 0x90, 0x6F, 0xA3, 0xA5, VK_LWIN, VK_RWIN}

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


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD),
                ("scanCode", wintypes.DWORD),
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
user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
user32.MapVirtualKeyW.restype = wintypes.UINT
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


def describe_hotkey(modifiers, target, is_mouse):
    """Human-readable form of a parsed hotkey, for the log."""
    names = [name for flag, name in ((MOD_CONTROL, "Ctrl"), (MOD_ALT, "Alt"),
                                     (MOD_SHIFT, "Shift"), (MOD_WIN, "Win"))
             if modifiers & flag]
    if is_mouse:
        names.append("XButton1" if target == XBUTTON1 else "XButton2")
        return "+".join(names)
    scan, extended = scan_code_for(target)
    names.append(f"vk 0x{target:02X} (scan 0x{scan:02X}{', extended' if extended else ''})")
    return "+".join(names)


def is_down(vk):
    """True while the key is physically held, regardless of focus."""
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def scan_code_for(vk):
    """Returns (scan_code, is_extended) for a virtual key.

    SendInput does not fill the scan code in for us. Anything that identifies
    keys by scan code rather than virtual key -- games, and the low-level hooks
    voice apps like Discord use for their global keybinds -- silently drops
    events that arrive with wScan == 0, which is why forwarding looked like a
    no-op even though SendInput reported success.
    """
    mapped = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC_EX)
    extended = (mapped >> 8) in (0xE0, 0xE1) or vk in EXTENDED_VKS
    return mapped & 0xFF, extended


def _key_input(vk, keyup):
    scan, extended = scan_code_for(vk)
    flags = KEYEVENTF_KEYUP if keyup else 0
    if extended:
        flags |= KEYEVENTF_EXTENDEDKEY
    item = INPUT(type=INPUT_KEYBOARD)
    item.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0,
                         dwExtraInfo=INJECTED_SIGNATURE)
    return item


def _xbutton_input(xbutton, keyup):
    item = INPUT(type=INPUT_MOUSE)
    item.mi = MOUSEINPUT(dx=0, dy=0, mouseData=xbutton,
                         dwFlags=MOUSEEVENTF_XUP if keyup else MOUSEEVENTF_XDOWN,
                         time=0, dwExtraInfo=INJECTED_SIGNATURE)
    return item


def modifiers_held(modifiers):
    """Exact match: every modifier in the combo is held and no other one is."""
    for flag, generic, _send_vk, sides in MODIFIERS:
        held = any(is_down(vk) for vk in sides) if generic == VK_LWIN else is_down(generic)
        if bool(modifiers & flag) != held:
            return False
    return True


class HotkeyListenerThread(threading.Thread):
    """Owns a Win32 message loop. Keyboard hotkeys go through RegisterHotKey,
    with a WH_KEYBOARD_LL hook as fallback when the combo is already owned by
    another process; thumb-button hotkeys always need a low-level mouse hook,
    which RegisterHotKey cannot express."""

    def __init__(self, hotkey_str, trigger_callback):
        super().__init__()
        self.hotkey_str = hotkey_str
        self.callback = trigger_callback
        self.running = True
        self.daemon = True
        self.error = None  # set when the hotkey could not be installed at all
        self._thread_id = None
        self._started = threading.Event()
        self._modifiers = 0
        self._target = 0
        self._hook_ref = None  # must outlive the hook or Windows calls into freed memory
        self._key_down = False
        self._key_swallowed = False

    def run(self):
        self._thread_id = kernel32.GetCurrentThreadId()
        self._started.set()

        try:
            self._modifiers, self._target, is_mouse = parse_hotkey_string(self.hotkey_str)
        except Exception as e:
            self.error = f"atalho '{self.hotkey_str}' inválido no Windows: {e}"
            logger.error(f"Failed to parse or map hotkey '{self.hotkey_str}': {e}")
            return

        described = describe_hotkey(self._modifiers, self._target, is_mouse)
        hook = None
        registered = False

        if is_mouse:
            logger.info(f"Hooking global mouse button '{self.hotkey_str}' -> {described}")
            hook = self._install_hook(WH_MOUSE_LL, self._on_mouse_event)
            if not hook:
                return
        else:
            logger.info(f"Registering global hotkey '{self.hotkey_str}' -> {described}")
            registered = bool(user32.RegisterHotKey(None, HOTKEY_ID,
                                                    self._modifiers | MOD_NOREPEAT,
                                                    self._target))
            if not registered:
                err = ctypes.get_last_error()
                reason = ("another application already owns this combination"
                          if err == ERROR_HOTKEY_ALREADY_REGISTERED
                          else ctypes.FormatError(err).strip())
                # RegisterHotKey is picky: it refuses combos another process
                # grabbed first and combos the shell reserves. A low-level
                # keyboard hook sees the key either way, so fall back to it
                # instead of leaving the app with no hotkey at all.
                logger.warning(f"RegisterHotKey failed for '{self.hotkey_str}' "
                               f"(error {err}: {reason}); falling back to WH_KEYBOARD_LL")
                hook = self._install_hook(WH_KEYBOARD_LL, self._on_key_event)
                if not hook:
                    return
                logger.info(f"Global hotkey '{self.hotkey_str}' active via keyboard hook.")

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

    def _install_hook(self, hook_id, proc):
        self._hook_ref = HOOKPROC(proc)
        hook = user32.SetWindowsHookExW(hook_id, self._hook_ref,
                                        kernel32.GetModuleHandleW(None), 0)
        if not hook:
            err = ctypes.get_last_error()
            self.error = (f"não foi possível registrar o atalho '{self.hotkey_str}' "
                          f"(erro {err}: {ctypes.FormatError(err).strip()})")
            logger.error(f"Failed to install hook {hook_id}: error {err} "
                         f"({ctypes.FormatError(err).strip()})")
        return hook

    def _on_key_event(self, n_code, w_param, l_param):
        if n_code == HC_ACTION:
            info = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            if info.dwExtraInfo != INJECTED_SIGNATURE and info.vkCode == self._target:
                if w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    if modifiers_held(self._modifiers):
                        self._key_swallowed = True
                        if not self._key_down:  # ignore auto-repeat, like MOD_NOREPEAT
                            self._key_down = True
                            logger.info("Global keyboard hotkey pressed! Triggering callback...")
                            self.callback()
                        return 1
                elif w_param in (WM_KEYUP, WM_SYSKEYUP):
                    self._key_down = False
                    if self._key_swallowed:
                        # Swallow the release too, otherwise the focused app
                        # sees an unpaired key-up.
                        self._key_swallowed = False
                        return 1
        return user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _on_mouse_event(self, n_code, w_param, l_param):
        if n_code == HC_ACTION and w_param in (WM_XBUTTONDOWN, WM_XBUTTONUP):
            info = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            xbutton = (info.mouseData >> 16) & 0xFFFF
            if (info.dwExtraInfo != INJECTED_SIGNATURE
                    and xbutton == self._target
                    and modifiers_held(self._modifiers)):
                if w_param == WM_XBUTTONDOWN:
                    logger.info("Global mouse hotkey pressed! Triggering callback...")
                    self.callback()
                # Swallow both halves of the click to match the X11 grab, which
                # keeps the button from also reaching the focused window.
                return 1
        return user32.CallNextHookEx(None, n_code, w_param, l_param)

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
        self.last_error = None

    def create_listener(self, hotkey_str, callback):
        return HotkeyListenerThread(hotkey_str, callback)

    def send_hotkey(self, hotkey_str):
        """Simulates a hotkey globally using SendInput."""
        try:
            modifiers, target, is_mouse = parse_hotkey_string(hotkey_str)
        except Exception as e:
            self.last_error = f"atalho do Discord '{hotkey_str}' inválido: {e}"
            logger.error(f"Failed to parse or resolve hotkey '{hotkey_str}': {e}")
            return False

        logger.info(f"Simulating hotkey '{hotkey_str}' -> "
                    f"{describe_hotkey(modifiers, target, is_mouse)} via SendInput...")

        events = []

        # 1. Lift every modifier the user is physically holding that is not part
        #    of the combo we are about to send. The app hotkey usually fires
        #    while Ctrl/Alt are still down, and those keys stay in the input
        #    state: sending "Ctrl+Shift+F12" from under a held "Ctrl+Alt+M" puts
        #    Ctrl+Alt+Shift+F12 on the wire, which no longer matches Discord's
        #    keybind. This is why forwarding did nothing when triggered by the
        #    hotkey.
        wanted = {generic for flag, generic, _send, _sides in MODIFIERS if modifiers & flag}
        stuck = []
        for _flag, generic, _send_vk, sides in MODIFIERS:
            if generic in wanted:
                continue
            for side in sides:
                if is_down(side):
                    stuck.append(side)
                    events.append(_key_input(side, keyup=True))
        if stuck:
            logger.info(f"Releasing {len(stuck)} held modifier(s) before forwarding.")

        # 2. The trigger key itself may still be held down when the app hotkey
        #    and the Discord hotkey share a key; release it so the tap below
        #    reads as a fresh press rather than an auto-repeat.
        if not is_mouse and target not in wanted and is_down(target):
            events.append(_key_input(target, keyup=True))

        # A modifier the user already holds is genuinely down in the input
        # state, so re-pressing it only adds an auto-repeat -- and releasing it
        # afterwards would leave the system thinking Ctrl is up while the key is
        # still physically down. Reuse it as-is instead.
        pressed = []
        for flag, generic, send_vk, _sides in MODIFIERS:
            if modifiers & flag and not is_down(generic):
                pressed.append(send_vk)
                events.append(_key_input(send_vk, keyup=False))

        if is_mouse:
            events.append(_xbutton_input(target, keyup=False))
            events.append(_xbutton_input(target, keyup=True))
        else:
            events.append(_key_input(target, keyup=False))
            events.append(_key_input(target, keyup=True))

        events.extend(_key_input(vk, keyup=True) for vk in reversed(pressed))
        # 3. Put the physically held modifiers back so the user's Ctrl/Alt keeps
        #    working in whatever window is focused.
        events.extend(_key_input(vk, keyup=False) for vk in reversed(stuck))

        array = (INPUT * len(events))(*events)
        sent = user32.SendInput(len(events), array, ctypes.sizeof(INPUT))
        if sent != len(events):
            err = ctypes.get_last_error()
            # Blocked input, or the foreground app runs at a higher integrity
            # level than we do (UIPI) -- typically Discord started as admin
            # while Livedot did not.
            self.last_error = (f"o Windows bloqueou o envio do atalho (erro {err}: "
                               f"{ctypes.FormatError(err).strip()}). Se o Discord "
                               f"roda como administrador, execute o Livedot como "
                               f"administrador também.")
            logger.error(f"SendInput delivered {sent}/{len(events)} events: "
                         f"error {err} ({ctypes.FormatError(err).strip()})")
            return False

        self.last_error = None
        logger.info("Hotkey simulation complete.")
        return True

    def close(self):
        pass
