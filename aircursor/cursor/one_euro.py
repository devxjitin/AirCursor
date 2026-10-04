"""One Euro Filter (Casiez et al., CHI 2012): low jitter when slow, low lag when fast."""

from __future__ import annotations

import math


class OneEuroFilter:
    """Filters a scalar signal sampled at irregular times (seconds)."""

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.0, d_cutoff: float = 1.0) -> None:
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._x: float | None = None
        self._dx = 0.0
        self._t = 0.0

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def reset(self) -> None:
        self._x = None
        self._dx = 0.0

    def __call__(self, x: float, t: float) -> float:
        if self._x is None or t <= self._t:
            self._x, self._dx, self._t = x, 0.0, t
            return x
        dt = t - self._t
        raw_dx = (x - self._x) / dt
        a_d = self._alpha(self.d_cutoff, dt)
        self._dx += a_d * (raw_dx - self._dx)
        cutoff = self.min_cutoff + self.beta * abs(self._dx)
        a = self._alpha(cutoff, dt)
        self._x += a * (x - self._x)
        self._t = t
        return self._x
