"""Smoothed frames-per-second counter."""

from __future__ import annotations

import time
from collections.abc import Callable


class FpsCounter:
    """Exponentially smoothed FPS over successive ``tick`` calls."""

    def __init__(self, smoothing: float = 0.9, clock: Callable[[], float] = time.perf_counter):
        self._smoothing = smoothing
        self._clock = clock
        self._last: float | None = None
        self.fps = 0.0

    def tick(self) -> float:
        now = self._clock()
        if self._last is not None and now > self._last:
            inst = 1.0 / (now - self._last)
            self.fps = (
                inst
                if self.fps == 0.0
                else (self._smoothing * self.fps + (1 - self._smoothing) * inst)
            )
        self._last = now
        return self.fps
