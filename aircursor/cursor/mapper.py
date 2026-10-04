"""Map a fingertip position in the camera image to a screen position."""

from __future__ import annotations

from dataclasses import dataclass

from aircursor.cursor.one_euro import OneEuroFilter


@dataclass(frozen=True)
class ActiveRegion:
    """Sub-rectangle of the (mirrored) camera image, in normalised coords, that spans the screen.

    A region smaller than the full frame means you only need to move your hand a short
    distance, and the cursor can still reach the screen edges.
    """

    left: float = 0.2
    top: float = 0.15
    right: float = 0.8
    bottom: float = 0.7

    def to_unit(self, x: float, y: float) -> tuple[float, float]:
        u = (x - self.left) / (self.right - self.left)
        v = (y - self.top) / (self.bottom - self.top)
        return min(max(u, 0.0), 1.0), min(max(v, 0.0), 1.0)


DEFAULT_REGION = ActiveRegion()


class CursorMapper:
    """Image coords -> smoothed screen pixel coords."""

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        region: ActiveRegion = DEFAULT_REGION,
        min_cutoff: float = 1.5,
        beta: float = 8.0,
        mirror: bool = True,
    ) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.region = region
        self.mirror = mirror
        self._fx = OneEuroFilter(min_cutoff, beta)
        self._fy = OneEuroFilter(min_cutoff, beta)

    def reset(self) -> None:
        """Forget filter history (call when tracking resumes after a pause)."""
        self._fx.reset()
        self._fy.reset()

    def map(self, x: float, y: float, t: float) -> tuple[int, int]:
        """``x``/``y`` are normalised image coordinates of the raw (un-mirrored) frame."""
        if self.mirror:
            x = 1.0 - x
        u, v = self.region.to_unit(x, y)
        u, v = self._fx(u, t), self._fy(v, t)
        return (
            round(u * (self.screen_w - 1)),
            round(v * (self.screen_h - 1)),
        )
