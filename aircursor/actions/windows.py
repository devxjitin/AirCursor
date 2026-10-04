"""Windows input backend using the Win32 API via ctypes (no extra dependencies)."""

from __future__ import annotations

import ctypes

_SM_CXSCREEN = 0
_SM_CYSCREEN = 1
_MOUSEEVENTF_LEFTDOWN = 0x0002
_MOUSEEVENTF_LEFTUP = 0x0004
_MOUSEEVENTF_RIGHTDOWN = 0x0008
_MOUSEEVENTF_RIGHTUP = 0x0010
_MOUSEEVENTF_WHEEL = 0x0800
_MOUSEEVENTF_HWHEEL = 0x01000
_VK_CONTROL = 0x11
_KEYEVENTF_KEYUP = 0x0002
_FLAGS = {
    "left": (_MOUSEEVENTF_LEFTDOWN, _MOUSEEVENTF_LEFTUP),
    "right": (_MOUSEEVENTF_RIGHTDOWN, _MOUSEEVENTF_RIGHTUP),
}


class WindowsBackend:
    def __init__(self) -> None:
        self._user32 = ctypes.windll.user32  # type: ignore[attr-defined,unused-ignore]
        # Without this, coordinates are DPI-virtualised and the cursor misses on scaled displays.
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # type: ignore[attr-defined,unused-ignore]
        except (AttributeError, OSError):
            self._user32.SetProcessDPIAware()

    def screen_size(self) -> tuple[int, int]:
        return self._user32.GetSystemMetrics(_SM_CXSCREEN), self._user32.GetSystemMetrics(
            _SM_CYSCREEN
        )

    def move_to(self, x: int, y: int) -> None:
        self._user32.SetCursorPos(int(x), int(y))

    def click(self, x: int, y: int, button: str = "left") -> None:
        self.move_to(x, y)
        down, up = _FLAGS[button]
        self._user32.mouse_event(down, 0, 0, 0, 0)
        self._user32.mouse_event(up, 0, 0, 0, 0)

    def button_down(self, button: str = "left") -> None:
        self._user32.mouse_event(_FLAGS[button][0], 0, 0, 0, 0)

    def button_up(self, button: str = "left") -> None:
        self._user32.mouse_event(_FLAGS[button][1], 0, 0, 0, 0)

    def scroll(self, dx: int, dy: int) -> None:
        if dy:
            self._user32.mouse_event(_MOUSEEVENTF_WHEEL, 0, 0, dy, 0)
        if dx:
            self._user32.mouse_event(_MOUSEEVENTF_HWHEEL, 0, 0, dx, 0)

    def zoom(self, dy: int) -> None:
        if not dy:
            return
        self._user32.keybd_event(_VK_CONTROL, 0, 0, 0)
        try:
            self._user32.mouse_event(_MOUSEEVENTF_WHEEL, 0, 0, dy, 0)
        finally:
            self._user32.keybd_event(_VK_CONTROL, 0, _KEYEVENTF_KEYUP, 0)
