"""Synthetic hands for gesture tests (upright, thumb on the image-left side)."""

from __future__ import annotations

import numpy as np

from aircursor.tracking.landmarks import Hand

_FINGER_X = {"index": 0.45, "middle": 0.50, "ring": 0.55, "pinky": 0.60}
_FINGER_BASE = {"index": 5, "middle": 9, "ring": 13, "pinky": 17}


def make_hand(
    thumb: bool = False,
    index: bool = False,
    middle: bool = False,
    ring: bool = False,
    pinky: bool = False,
    offset: tuple[float, float] = (0.0, 0.0),
    pinch: bool = False,
    pinch_middle: bool = False,
) -> Hand:
    pts = np.zeros((21, 3), dtype=np.float32)
    pts[0] = (0.5, 0.9, 0)
    pts[1] = (0.42, 0.85, 0)
    pts[2] = (0.37, 0.78, 0)
    pts[3] = (0.33, 0.72, 0)
    pts[4] = (0.27, 0.66, 0) if thumb else (0.45, 0.68, 0)
    ext = {"index": index, "middle": middle, "ring": ring, "pinky": pinky}
    for name, base in _FINGER_BASE.items():
        x = _FINGER_X[name]
        ys = (0.60, 0.50, 0.42, 0.35) if ext[name] else (0.60, 0.50, 0.58, 0.66)
        for i, y in enumerate(ys):
            pts[base + i] = (x, y, 0)
    if pinch:
        pts[4] = pts[8] + (0.01, 0.02, 0)  # thumb tip touching the index tip
    if pinch_middle:
        pts[4] = pts[12] + (0.01, 0.02, 0)  # thumb tip touching the middle tip
    pts[:, 0] += offset[0]
    pts[:, 1] += offset[1]
    return Hand(points=pts, handedness="Right", score=0.99)


POINT = dict(index=True)
TWO = dict(index=True, middle=True)
PALM = dict(thumb=True, index=True, middle=True, ring=True, pinky=True)
FIST: dict[str, bool] = {}
