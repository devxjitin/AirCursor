"""Two-finger scrolling: hand motion -> mouse wheel units."""

from __future__ import annotations

from aircursor.cursor.one_euro import OneEuroFilter


class ScrollTracker:
    """Converts motion of a point (in normalised image coords) into wheel units.

    Motion is divided by hand size so the feel doesn't depend on distance from the camera.
    Only the dominant axis scrolls on each frame, so a mostly-vertical swipe can't also
    drift sideways. Faster movement scrolls disproportionately further (``accel``).

    Directions follow a physical wheel seen in a mirror: hand up = scroll up,
    hand right = scroll right. ``invert`` flips both ("natural"/touch-style scrolling).
    """

    def __init__(
        self,
        gain: float = 800.0,  # wheel units per hand-size of travel (120 units = one notch)
        accel: float = 0.5,
        dead_zone: float = 0.002,  # per-frame travel, in hand sizes, ignored as jitter
        invert: bool = False,
    ) -> None:
        self.gain = gain
        self.accel = accel
        self.dead_zone = dead_zone
        self.invert = invert
        self._fx = OneEuroFilter(min_cutoff=2.0, beta=0.0)
        self._fy = OneEuroFilter(min_cutoff=2.0, beta=0.0)
        self.reset()

    def reset(self) -> None:
        """Call whenever scrolling stops, so the next scroll starts from rest."""
        self._fx.reset()
        self._fy.reset()
        self._last: tuple[float, float, float] | None = None
        self._acc_x = 0.0
        self._acc_y = 0.0

    def update(self, t: float, x: float, y: float, scale: float) -> tuple[int, int]:
        """Return ``(dx, dy)`` wheel units to send this frame (usually 0 or a few)."""
        fx, fy = self._fx(x, t), self._fy(y, t)
        last, self._last = self._last, (fx, fy, t)
        if last is None or t <= last[2]:
            return 0, 0
        dt = t - last[2]
        mx = (fx - last[0]) / scale  # hand-size units; image x grows to the user's left
        my = (fy - last[1]) / scale
        # Mirror x (image is not mirrored here) and flip y so up/right are positive.
        mx, my = -mx, -my
        if self.invert:
            mx, my = -mx, -my
        if abs(mx) >= abs(my):
            my = 0.0
        else:
            mx = 0.0
        major = max(abs(mx), abs(my))
        if major < self.dead_zone:
            return 0, 0
        gain = self.gain * (1.0 + self.accel * major / dt)
        self._acc_x += mx * gain
        self._acc_y += my * gain
        out_x, out_y = int(self._acc_x), int(self._acc_y)
        self._acc_x -= out_x
        self._acc_y -= out_y
        return out_x, out_y
