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


def draw_status(frame: Frame, fps: float, hand: Hand | None, pose: str | None = None) -> None:
    """Draw the FPS counter, hand status and (optionally) the current pose in place."""
    status = f"{hand.handedness} hand ({hand.score:.2f})" if hand else "no hand"
    cv2.putText(frame, f"FPS: {fps:5.1f}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, _WHITE, 2)
    cv2.putText(frame, status, (10, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.6, _WHITE, 1)
    if pose is not None:
        cv2.putText(frame, f"pose: {pose}", (10, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.6, _YELLOW, 2)
