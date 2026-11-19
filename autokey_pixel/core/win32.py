"""Thin ctypes wrappers around the Win32 APIs used by the app.

Everything Windows-specific lives here so the rest of the code can be
imported (and unit-tested) on any OS. On non-Windows platforms the
functions raise ``OSError``.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

IS_WINDOWS = sys.platform == "win32"

# --- constants -------------------------------------------------------------
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
MAPVK_VK_TO_VSC_EX = 4
CLR_INVALID = 0xFFFFFFFF

ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


if IS_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.SendInput.restype = wintypes.UINT
    user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
    user32.MapVirtualKeyW.restype = wintypes.UINT
    user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.GetDC.argtypes = (wintypes.HWND,)
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = (wintypes.HWND, wintypes.HDC)
    user32.ReleaseDC.restype = ctypes.c_int
    gdi32.GetPixel.argtypes = (wintypes.HDC, ctypes.c_int, ctypes.c_int)
    gdi32.GetPixel.restype = wintypes.DWORD
else:  # pragma: no cover - only used on Windows
    user32 = gdi32 = None


def _require_windows() -> None:
    if not IS_WINDOWS:
        raise OSError("Esta função só está disponível no Windows.")


# --- DPI -------------------------------------------------------------------
def set_dpi_awareness() -> None:
    """Make the process per-monitor DPI aware so coordinates/pixels are physical.

    Must run before any GUI toolkit or library that touches DPI is imported.
    Silently ignores failures (e.g. awareness already set).
    """
    if not IS_WINDOWS:
        return
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


# --- cursor / pixel -----------------------------------------------------------
def get_cursor_pos() -> tuple[int, int]:
    _require_windows()
    pt = wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(pt)):
        raise ctypes.WinError(ctypes.get_last_error())
    return pt.x, pt.y


def get_pixel(x: int, y: int) -> tuple[int, int, int]:
    _require_windows()
    hdc = user32.GetDC(None)
    if not hdc:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        color = gdi32.GetPixel(hdc, x, y)
    finally:
        user32.ReleaseDC(None, hdc)
    if color == CLR_INVALID:
        raise OSError(f"Não foi possível ler o pixel em ({x}, {y}).")
    return color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF


# --- keyboard injection ---------------------------------------------------
def vk_to_scan(vk: int) -> tuple[int, bool]:
    """Return (scan_code, is_extended) for a virtual-key code."""
    _require_windows()
    sc = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC_EX)
    extended = (sc & 0xFF00) in (0xE000, 0xE100)
    return sc & 0xFF, extended


def send_key(vk: int, up: bool, use_scancode: bool = True) -> None:
    """Inject a single key-down or key-up event with SendInput."""
    _require_windows()
    scan, extended = vk_to_scan(vk)
    flags = KEYEVENTF_KEYUP if up else 0
    if extended:
        flags |= KEYEVENTF_EXTENDEDKEY

    inp = INPUT(type=INPUT_KEYBOARD)
    if use_scancode and scan:
        inp.ki = KEYBDINPUT(wVk=0, wScan=scan, dwFlags=flags | KEYEVENTF_SCANCODE)
    else:
        inp.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags)

    sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    if sent != 1:
        raise OSError(
            "SendInput foi bloqueado. Se a janela alvo roda como administrador, "
            "execute o AutoKey Pixel como administrador também."
        )


# --- elevation --------------------------------------------------------------
def is_admin() -> bool:
    if not IS_WINDOWS:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def relaunch_as_admin() -> bool:
    """Start a new elevated copy of this program. Returns True on success."""
    _require_windows()
    if getattr(sys, "frozen", False):
        exe, params = sys.executable, " ".join(f'"{a}"' for a in sys.argv[1:])
    else:
        exe = sys.executable
        params = " ".join(f'"{a}"' for a in sys.argv)
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    return rc > 32
