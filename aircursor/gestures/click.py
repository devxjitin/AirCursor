"""Turns a stream of pinch states into single / double click events."""

from __future__ import annotations

from enum import Enum


class ClickKind(Enum):
    SINGLE = "single"
    DOUBLE = "double"


class ClickDetector:
    """A *tap* is a pinch that is released within ``max_hold`` seconds; the click fires on release.

    A second tap within ``double_window`` seconds of the first is reported as DOUBLE. Both taps
    still reach the OS as ordinary clicks at the same position, which Windows turns into a
    double click (keep ``double_window`` below the system double-click time, 0.5 s by default).
    Pinches held longer than ``max_hold`` are not clicks (they become drag in a later phase).
    """

    _IDLE, _PRESSED, _IGNORE = range(3)

    def __init__(
        self, min_hold: float = 0.05, max_hold: float = 0.5, double_window: float = 0.45
    ) -> None:
        self.min_hold = min_hold
        self.max_hold = max_hold
        self.double_window = double_window
        self._state = self._IDLE
        self._pressed_at = 0.0
        self._last_tap: float | None = None

    @property
    def pressed(self) -> bool:
        return self._state == self._PRESSED

    def update(self, t: float, pinched: bool, active: bool) -> ClickKind | None:
        """``t`` in seconds. ``active`` is False when the hand is gone or not in pointing shape."""
        if self._state == self._IDLE:
            if active and pinched:
                self._state, self._pressed_at = self._PRESSED, t
        elif self._state == self._PRESSED:
            if not active:
                self._state = self._IGNORE if pinched else self._IDLE
            elif not pinched:
                self._state = self._IDLE
                return self._release(t)
        elif not pinched:  # _IGNORE: wait for the pinch to open before arming again
            self._state = self._IDLE
        return None

    def _release(self, t: float) -> ClickKind | None:
        held = t - self._pressed_at
        if not (self.min_hold <= held <= self.max_hold):
            return None
        if self._last_tap is not None and t - self._last_tap <= self.double_window:
            self._last_tap = None
            return ClickKind.DOUBLE
        self._last_tap = t
        return ClickKind.SINGLE
