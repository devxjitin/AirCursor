"""Windows input backend using the Win32 API via ctypes (no extra dependencies)."""

from __future__ import annotations

import ctypes

_SM_CXSCREEN = 0
_SM_CYSCREEN = 1


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
