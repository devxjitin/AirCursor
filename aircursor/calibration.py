"""Calibration: learn the part of the camera image the user can comfortably reach.

The user holds an index-finger point at the top-left, then the bottom-right, of the area they
want to use. Each corner is captured automatically once the fingertip has been still for
``hold`` seconds. Coordinates are in the *mirrored* image, like ``cursor.region``.
"""

from __future__ import annotations

import math

from aircursor.cursor.mapper import ActiveRegion

STEPS = ("TOP-LEFT", "BOTTOM-RIGHT")
MIN_SIZE = 0.15  # smallest accepted region, as a fraction of the image per axis


class CalibrationSession:
    def __init__(self, hold: float = 1.5, still: float = 0.02) -> None:
        self.hold = hold
        self.still = still
        self.step = 0
        self.points: list[tuple[float, float]] = []
        self.message = ""
        self._anchor: tuple[float, float] | None = None
        self._since = 0.0

    @property
    def done(self) -> bool:
        return self.step >= len(STEPS)

    @property
    def prompt(self) -> str:
        if self.done:
            return "Done"
        return f"Point at the {STEPS[self.step]} of your comfortable area and hold still"

    @property
    def region(self) -> ActiveRegion:
        (x0, y0), (x1, y1) = self.points
        return ActiveRegion(x0, y0, x1, y1)

    def update(self, tip: tuple[float, float] | None, t: float) -> float:
        """Feed the mirrored fingertip (``None`` if not pointing). Returns progress 0..1."""
        if self.done:
            return 1.0
        if tip is None:
            self._anchor = None
            return 0.0
        if self._anchor is None or math.dist(tip, self._anchor) > self.still:
            self._anchor, self._since = tip, t
            return 0.0
        progress = min((t - self._since) / self.hold, 1.0)
        if progress >= 1.0:
            self._capture(self._anchor)
            self._anchor = None
            return 1.0
        return progress

    def _capture(self, point: tuple[float, float]) -> None:
        if self.step == 1:
            (x0, y0) = self.points[0]
            if point[0] - x0 < MIN_SIZE or point[1] - y0 < MIN_SIZE:
                self.message = "Too small, or not below/right of the first corner. Try again."
                return
        self.message = ""
        self.points.append(point)
        self.step += 1
