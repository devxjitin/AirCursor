"""Debug drawing helpers."""

from __future__ import annotations

import cv2

from aircursor.capture.source import Frame
from aircursor.cursor.mapper import ActiveRegion
from aircursor.tracking.landmarks import CONNECTIONS, Hand, Landmark

_GREEN = (0, 220, 0)
_RED = (0, 0, 255)
_WHITE = (255, 255, 255)
_YELLOW = (0, 220, 255)
_FINGERTIPS = (
    Landmark.THUMB_TIP,
    Landmark.INDEX_TIP,
    Landmark.MIDDLE_TIP,
    Landmark.RING_TIP,
    Landmark.PINKY_TIP,
)


def draw_hand(frame: Frame, hand: Hand) -> None:
    """Draw the skeleton and joints of ``hand`` onto ``frame`` in place."""
    h, w = frame.shape[:2]
    pts = hand.pixel_points(w, h)
    for a, b in CONNECTIONS:
        cv2.line(frame, tuple(int(v) for v in pts[a]), tuple(int(v) for v in pts[b]), _GREEN, 2)
    for i, (x, y) in enumerate(pts):
        radius = 6 if i in _FINGERTIPS else 3
        cv2.circle(frame, (int(x), int(y)), radius, _RED, -1)


def draw_region(frame: Frame, region: ActiveRegion) -> None:
    """Outline the active region (the part of the image that spans the whole screen)."""
    h, w = frame.shape[:2]
    p1 = (int(region.left * w), int(region.top * h))
    p2 = (int(region.right * w), int(region.bottom * h))
    cv2.rectangle(frame, p1, p2, _YELLOW, 1)


def draw_status(
    frame: Frame,
    fps: float,
    hand: Hand | None,
    pose: str | None = None,
    flash: str | None = None,
) -> None:
    """Draw the FPS counter, hand status and (optionally) the current pose in place."""
    status = f"{hand.handedness} hand ({hand.score:.2f})" if hand else "no hand"
    cv2.putText(frame, f"FPS: {fps:5.1f}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, _WHITE, 2)
    cv2.putText(frame, status, (10, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.6, _WHITE, 1)
    if pose is not None:
        cv2.putText(frame, f"pose: {pose}", (10, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.6, _YELLOW, 2)
    if flash:
        cv2.putText(frame, flash, (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.9, _GREEN, 3)


_RED = (0, 0, 255)
_ORANGE = (0, 165, 255)


def draw_lock(frame: Frame, locked: bool, progress: float, hold_seconds: float) -> None:
    """Show the lock state, and a progress bar while a fist is being held to toggle it."""
    h, w = frame.shape[:2]
    if locked:
        cv2.rectangle(frame, (0, h - 34), (w, h), _RED, -1)
        msg = f"LOCKED - hold a fist {hold_seconds:g}s to unlock"
        cv2.putText(frame, msg, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, _WHITE, 2)
    if progress > 0:
        x0, y0, bw = 10, h - 60, w - 20
        cv2.rectangle(frame, (x0, y0), (x0 + bw, y0 + 10), _WHITE, 1)
        cv2.rectangle(frame, (x0, y0), (x0 + int(bw * progress), y0 + 10), _ORANGE, -1)


_GREY = (200, 200, 200)


def draw_calibration(
    frame: Frame, prompt: str, message: str, progress: float, points: list[tuple[float, float]]
) -> None:
    """Draw the calibration instructions, captured corners and hold-still progress bar."""
    h, w = frame.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    for px, py in points:
        cv2.drawMarker(frame, (int(px * w), int(py * h)), _YELLOW, cv2.MARKER_CROSS, 30, 3)
    cv2.putText(frame, prompt, (10, 28), font, 0.65, _WHITE, 2)
    cv2.putText(frame, "(index finger out, other fingers curled)", (10, 54), font, 0.5, _GREY, 1)
    if message:
        cv2.putText(frame, message, (10, 80), font, 0.55, _RED, 2)
    bar_end = 10 + int((w - 20) * progress)
    cv2.rectangle(frame, (10, h - 24), (bar_end, h - 10), _GREEN, -1)
