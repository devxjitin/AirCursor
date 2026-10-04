"""Hand landmark data types, independent of MediaPipe."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import numpy as np
from numpy.typing import NDArray


class Landmark(IntEnum):
    """Indices of the 21 MediaPipe hand landmarks."""

    WRIST = 0
    THUMB_CMC = 1
    THUMB_MCP = 2
    THUMB_IP = 3
    THUMB_TIP = 4
    INDEX_MCP = 5
    INDEX_PIP = 6
    INDEX_DIP = 7
    INDEX_TIP = 8
    MIDDLE_MCP = 9
    MIDDLE_PIP = 10
    MIDDLE_DIP = 11
    MIDDLE_TIP = 12
    RING_MCP = 13
    RING_PIP = 14
    RING_DIP = 15
    RING_TIP = 16
    PINKY_MCP = 17
    PINKY_PIP = 18
    PINKY_DIP = 19
    PINKY_TIP = 20


# Skeleton edges used for drawing.
CONNECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)  # fmt: skip


@dataclass(frozen=True)
class Hand:
    """One tracked hand.

    ``points`` is a (21, 3) float array: x and y are normalised to [0, 1] image
    coordinates (origin top-left), z is relative depth (smaller = closer to camera).
    """

    points: NDArray[np.float32]
    handedness: str  # "Left" or "Right", as seen by the person (image is not mirrored here)
    score: float

    def pixel_points(self, width: int, height: int) -> NDArray[np.int32]:
        """Return (21, 2) integer pixel coordinates for an image of the given size."""
        scale = np.array([width, height], dtype=np.float32)
        return (self.points[:, :2] * scale).astype(np.int32)

    def mirrored(self) -> Hand:
        """Return the hand flipped horizontally (matches a mirrored preview image)."""
        points = self.points.copy()
        points[:, 0] = 1.0 - points[:, 0]
        return Hand(points=points, handedness=self.handedness, score=self.score)
