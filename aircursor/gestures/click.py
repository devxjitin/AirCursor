"""Turns a stream of pinch states into click, double-click and drag events."""

from __future__ import annotations

from enum import Enum


class ClickKind(Enum):
    SINGLE = "single"
    DOUBLE = "double"
    DRAG_START = "drag_start"
    DRAG_END = "drag_end"


class ClickDetector:
    """A *tap* is a pinch released within ``max_hold`` seconds; the click fires on release.

    A second tap within ``double_window`` seconds of the first is reported as DOUBLE. Both taps
    still reach the OS as ordinary clicks at the same position, which Windows turns into a
    double click (keep ``double_window`` below the system double-click time, 0.5 s by default).

    With ``allow_drag``, a pinch held past ``max_hold`` becomes a drag: DRAG_START when the hold
    passes the threshold, DRAG_END when the pinch opens (or the hand has been gone for
    ``lost_grace`` seconds, so a mouse button can never stay stuck down).
    """

    _IDLE, _PRESSED, _DRAGGING, _IGNORE = range(4)

    def __init__(
        self,
        min_hold: float = 0.05,
        max_hold: float = 0.5,
        double_window: float = 0.45,
        allow_drag: bool = False,
        lost_grace: float = 0.3,
    ) -> None:
        self.min_hold = min_hold
        self.max_hold = max_hold
        self.double_window = double_window
        self.allow_drag = allow_drag
        self.lost_grace = lost_grace
        self._state = self._IDLE
        self._pressed_at = 0.0
        self._inactive_since: float | None = None
        self._last_tap: float | None = None

    @property
    def pressed(self) -> bool:
        return self._state == self._PRESSED

    @property
    def dragging(self) -> bool:
        return self._state == self._DRAGGING

    @property
    def held(self) -> bool:
        return self._state in (self._PRESSED, self._DRAGGING)

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
            elif self.allow_drag and t - self._pressed_at > self.max_hold:
                self._state, self._inactive_since = self._DRAGGING, None
                return ClickKind.DRAG_START
        elif self._state == self._DRAGGING:
            if active:
                self._inactive_since = None
            elif self._inactive_since is None:
                self._inactive_since = t
            lost = self._inactive_since is not None and t - self._inactive_since > self.lost_grace
            if not pinched or lost:
                self._state = self._IGNORE if pinched else self._IDLE
                return ClickKind.DRAG_END
        elif not pinched:  # _IGNORE: wait for the pinch to open before arming again
            self._state = self._IDLE
        return None

    def reset(self) -> ClickKind | None:
        """Abort any press; returns DRAG_END if a drag was in progress."""
        ended = ClickKind.DRAG_END if self.dragging else None
        self._state = self._IDLE
        return ended

    def _release(self, t: float) -> ClickKind | None:
        held = t - self._pressed_at
        if not (self.min_hold <= held <= self.max_hold):
            return None
        if self._last_tap is not None and t - self._last_tap <= self.double_window:
            self._last_tap = None
            return ClickKind.DOUBLE
        self._last_tap = t
        return ClickKind.SINGLE
