"""Two-finger scrolling: hand motion -> mouse wheel units, with optional flick inertia."""

from __future__ import annotations

import math

from aircursor.cursor.one_euro import OneEuroFilter


class ScrollTracker:
    """Converts motion of a point (in normalised image coords) into wheel units.

    Motion is divided by hand size so the feel doesn't depend on distance from the camera.
    Only the dominant axis scrolls on each frame, so a mostly-vertical swipe can't also
    drift sideways (``vertical_only`` forces vertical, used for zoom). Faster movement scrolls
    disproportionately further (``accel``).

    Directions follow a physical wheel seen in a mirror: hand up = scroll up,
    hand right = scroll right. ``invert`` flips both ("natural"/touch-style scrolling).

    Inertia: ``stop(coast=True)`` after a flick keeps scrolling with exponentially decaying
    speed (time constant ``inertia_time``); call ``coast`` once per frame until it is done.
    """

    _MIN_COAST_SPEED = 240.0  # wheel units/s needed to coast at all (2 notches/s)
    _END_SPEED = 40.0  # wheel units/s below which a coast ends

    def __init__(
        self,
        gain: float = 800.0,  # wheel units per hand-size of travel (120 units = one notch)
        accel: float = 0.5,
        dead_zone: float = 0.002,  # per-frame travel, in hand sizes, ignored as jitter
        invert: bool = False,
        inertia_time: float = 0.4,
        vertical_only: bool = False,
    ) -> None:
        self.gain = gain
        self.accel = accel
        self.dead_zone = dead_zone
        self.invert = invert
        self.inertia_time = inertia_time
        self.vertical_only = vertical_only
        self._fx = OneEuroFilter(min_cutoff=2.0, beta=0.0)
        self._fy = OneEuroFilter(min_cutoff=2.0, beta=0.0)
        self.reset()

    @property
    def coasting(self) -> bool:
        return self._coasting

    def reset(self) -> None:
        """Hard stop: forget everything, no inertia."""
        self._fx.reset()
        self._fy.reset()
        self._last: tuple[float, float, float] | None = None
        self._acc_x = 0.0
        self._acc_y = 0.0
        self._vx = 0.0  # smoothed wheel units per second, for inertia
        self._vy = 0.0
        self._coasting = False
        self._coast_t: float | None = None

    def stop(self, coast: bool = False) -> None:
        """Scrolling ended. With ``coast`` and enough speed, glide to a stop instead."""
        vx, vy = self._vx, self._vy
        self.reset()
        if coast and math.hypot(vx, vy) >= self._MIN_COAST_SPEED:
            self._vx, self._vy, self._coasting = vx, vy, True

    def cancel_coast(self) -> None:
        self.reset()

    def update(self, t: float, x: float, y: float, scale: float) -> tuple[int, int]:
        """Return ``(dx, dy)`` wheel units to send this frame (usually 0 or a few)."""
        self._coasting = False
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
        if self.vertical_only or abs(mx) < abs(my):
            mx = 0.0
        else:
            my = 0.0
        major = max(abs(mx), abs(my))
        if major < self.dead_zone:
            self._track_velocity(0.0, 0.0)
            return 0, 0
        gain = self.gain * (1.0 + self.accel * major / dt)
        ux, uy = mx * gain, my * gain
        self._track_velocity(ux / dt, uy / dt)
        self._acc_x += ux
        self._acc_y += uy
        return self._drain()

    def coast(self, t: float) -> tuple[int, int]:
        """Wheel units for this frame of a glide started by ``stop(coast=True)``."""
        if not self._coasting:
            return 0, 0
        if self._coast_t is None:
            self._coast_t = t
            return 0, 0
        dt = t - self._coast_t
        self._coast_t = t
        if dt <= 0:
            return 0, 0
        decay = math.exp(-dt / self.inertia_time)
        self._vx *= decay
        self._vy *= decay
        if math.hypot(self._vx, self._vy) < self._END_SPEED:
            self.reset()
            return 0, 0
        self._acc_x += self._vx * dt
        self._acc_y += self._vy * dt
        return self._drain()

    def _track_velocity(self, vx: float, vy: float) -> None:
        self._vx += 0.5 * (vx - self._vx)
        self._vy += 0.5 * (vy - self._vy)

    def _drain(self) -> tuple[int, int]:
        out_x, out_y = int(self._acc_x), int(self._acc_y)
        self._acc_x -= out_x
        self._acc_y -= out_y
        return out_x, out_y
