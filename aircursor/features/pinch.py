"""Thumb-to-index pinch measurement."""

from __future__ import annotations

import numpy as np

from aircursor.tracking.landmarks import Hand, Landmark


def hand_scale(hand: Hand) -> float:
    """Wrist-to-middle-knuckle distance: a size reference that survives distance from camera."""
    d = float(
        np.linalg.norm(hand.points[Landmark.WRIST, :2] - hand.points[Landmark.MIDDLE_MCP, :2])
    )
    return max(d, 1e-6)


def pinch_ratio(hand: Hand, finger_tip: int = Landmark.INDEX_TIP) -> float:
    """Thumb-tip to ``finger_tip`` distance as a fraction of hand size (0 = touching)."""
    d = float(np.linalg.norm(hand.points[Landmark.THUMB_TIP, :2] - hand.points[finger_tip, :2]))
    return d / hand_scale(hand)


def finger_reach(hand: Hand, tip: int, mcp: int) -> float:
    """Fingertip distance from the wrist relative to its knuckle's (<1: curled into the palm)."""
    wrist = hand.points[Landmark.WRIST, :2]
    t = float(np.linalg.norm(hand.points[tip, :2] - wrist))
    m = float(np.linalg.norm(hand.points[mcp, :2] - wrist))
    return t / max(m, 1e-6)


def index_reach(hand: Hand) -> float:
    return finger_reach(hand, Landmark.INDEX_TIP, Landmark.INDEX_MCP)


def middle_reach(hand: Hand) -> float:
    return finger_reach(hand, Landmark.MIDDLE_TIP, Landmark.MIDDLE_MCP)


class PinchDetector:
    """Schmitt trigger on the pinch ratio, so noise around one threshold cannot flicker."""

    def __init__(self, close_below: float = 0.30, open_above: float = 0.50) -> None:
        self.close_below = close_below
        self.open_above = open_above
        self.pinched = False

    def update(self, ratio: float, can_close: bool = True, force_open: bool = False) -> bool:
        """``can_close`` False blocks a new pinch (e.g. a fist, where thumb meets curled index).

        ``force_open`` ends a held pinch regardless of distance (the finger curled into the
        palm, where a tucked thumb would otherwise keep the pinch "closed" forever).
        """
        if self.pinched:
            if ratio > self.open_above or force_open:
                self.pinched = False
        elif ratio < self.close_below and can_close:
            self.pinched = True
        return self.pinched

    def reset(self) -> None:
        self.pinched = False
