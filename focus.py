"""Whether Discord's window has the focus, and bringing it to the front.

The unread-message badge clears once the user looks at Discord, and a click
on it takes them there. Both are best effort: any failure reads as "not
focused" or "not raised" and is logged.
"""

import os
import sys
import logging

logger = logging.getLogger("livedot.focus")

# Executable (Windows) or WM_CLASS (X11) names of the Discord builds.
DISCORD_NAMES = ("discord", "discordptb", "discordcanary")

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes as wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    SW_RESTORE = 9

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.EnumWindows.argtypes = (WNDENUMPROC, wintypes.LPARAM)
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    user32.IsIconic.argtypes = (wintypes.HWND,)
    user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD,
                                                    wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)

    def _is_discord(hwnd):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not handle:
            return False
        try:
            path = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(path))
            if not kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
                return False
            name = os.path.splitext(os.path.basename(path.value))[0].lower()
            return name in DISCORD_NAMES
        finally:
            kernel32.CloseHandle(handle)

    def discord_focused():
        hwnd = user32.GetForegroundWindow()
        return bool(hwnd) and _is_discord(hwnd)

    def raise_discord():
        found = []

        def collect(hwnd, _):
            if (user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd)
                    and _is_discord(hwnd)):
                found.append(hwnd)
                return False
            return True

        user32.EnumWindows(WNDENUMPROC(collect), 0)
        if not found:
            logger.info("No visible Discord window to raise.")
            return
        if user32.IsIconic(found[0]):
            user32.ShowWindow(found[0], SW_RESTORE)
        # Allowed because our overlay just received the click.
        user32.SetForegroundWindow(found[0])

else:
    from Xlib import X, protocol
    from Xlib.display import Display
    from Xlib.error import XError

    _display = None

    def _connection():
        global _display
        if _display is None:
            _display = Display()
        return _display

    def _reset():
        global _display
        try:
            if _display is not None:
                _display.close()
        except Exception:
            pass
        _display = None

    def _is_discord(display, window_id):
        window = display.create_resource_object("window", window_id)
        try:
            classes = window.get_wm_class() or ()
        except XError:
            return False  # closed while we looked
        return any(name.lower() in DISCORD_NAMES for name in classes)

    def discord_focused():
        try:
            display = _connection()
            root = display.screen().root
            prop = root.get_full_property(display.intern_atom("_NET_ACTIVE_WINDOW"),
                                          X.AnyPropertyType)
            return bool(prop and prop.value[0]) and _is_discord(display, prop.value[0])
        except Exception as e:
            logger.warning(f"Could not read the active window: {e}")
            _reset()
            return False

    def raise_discord():
        try:
            display = _connection()
            root = display.screen().root
            clients = root.get_full_property(display.intern_atom("_NET_CLIENT_LIST"),
                                             X.AnyPropertyType)
            for window_id in (clients.value if clients else ()):
                if _is_discord(display, window_id):
                    # Source 2 ("pager") asks the window manager to obey even
                    # though the request doesn't come from the focused app.
                    event = protocol.event.ClientMessage(
                        window=display.create_resource_object("window", window_id),
                        client_type=display.intern_atom("_NET_ACTIVE_WINDOW"),
                        data=(32, [2, X.CurrentTime, 0, 0, 0]))
                    root.send_event(event, event_mask=X.SubstructureRedirectMask
                                    | X.SubstructureNotifyMask)
                    display.flush()
                    return
            logger.info("No Discord window to raise.")
        except Exception as e:
            logger.warning(f"Could not raise Discord: {e}")
            _reset()
