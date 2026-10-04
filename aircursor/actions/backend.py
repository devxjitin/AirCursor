"""OS input abstraction. Everything above this layer is platform-independent."""

from __future__ import annotations

import sys
from typing import Protocol


class InputBackend(Protocol):
    def screen_size(self) -> tuple[int, int]: ...

    def move_to(self, x: int, y: int) -> None: ...

    def click(self, x: int, y: int) -> None:
        """Left-click at (x, y)."""


class RecordingBackend:
    """Does not touch the OS; records moves. Used for tests and ``--dry-run``."""

    def __init__(self, width: int = 1920, height: int = 1080) -> None:
        self._size = (width, height)
        self.moves: list[tuple[int, int]] = []
        self.clicks: list[tuple[int, int]] = []

    def screen_size(self) -> tuple[int, int]:
        return self._size

    def move_to(self, x: int, y: int) -> None:
        self.moves.append((x, y))

    def click(self, x: int, y: int) -> None:
        self.clicks.append((x, y))


def make_backend() -> InputBackend:
    """Return the real backend for this platform."""
    if sys.platform == "win32":
        from aircursor.actions.windows import WindowsBackend

        return WindowsBackend()
    raise NotImplementedError(
        f"No input backend for {sys.platform!r} yet (Windows only). Use --dry-run."
    )
