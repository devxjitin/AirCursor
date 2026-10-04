"""OS input abstraction. Everything above this layer is platform-independent."""

from __future__ import annotations

import sys
from typing import Protocol


class InputBackend(Protocol):
    def screen_size(self) -> tuple[int, int]: ...

    def move_to(self, x: int, y: int) -> None: ...

    def click(self, x: int, y: int, button: str = "left") -> None:
        """Click ``button`` ("left" or "right") at (x, y)."""

    def button_down(self, button: str = "left") -> None:
        """Press and hold a mouse button at the current cursor position."""

    def button_up(self, button: str = "left") -> None: ...

    def scroll(self, dx: int, dy: int) -> None:
        """Scroll by wheel units (120 = one notch). Positive dy = up, positive dx = right."""

    def zoom(self, dy: int) -> None:
        """Ctrl + wheel by ``dy`` wheel units (positive = zoom in)."""


class RecordingBackend:
    """Does not touch the OS; records moves. Used for tests and ``--dry-run``."""

    def __init__(self, width: int = 1920, height: int = 1080) -> None:
        self._size = (width, height)
        self.moves: list[tuple[int, int]] = []
        self.clicks: list[tuple[int, int]] = []  # left clicks
        self.right_clicks: list[tuple[int, int]] = []
        self.button_events: list[tuple[str, str]] = []  # ("down" | "up", button)
        self.scrolls: list[tuple[int, int]] = []
        self.zooms: list[int] = []

    def screen_size(self) -> tuple[int, int]:
        return self._size

    def move_to(self, x: int, y: int) -> None:
        self.moves.append((x, y))

    def click(self, x: int, y: int, button: str = "left") -> None:
        (self.clicks if button == "left" else self.right_clicks).append((x, y))

    def button_down(self, button: str = "left") -> None:
        self.button_events.append(("down", button))

    def button_up(self, button: str = "left") -> None:
        self.button_events.append(("up", button))

    def scroll(self, dx: int, dy: int) -> None:
        self.scrolls.append((dx, dy))

    def zoom(self, dy: int) -> None:
        self.zooms.append(dy)


def make_backend() -> InputBackend:
    """Return the real backend for this platform."""
    if sys.platform == "win32":
        from aircursor.actions.windows import WindowsBackend

        return WindowsBackend()
    raise NotImplementedError(
        f"No input backend for {sys.platform!r} yet (Windows only). Use --dry-run."
    )
