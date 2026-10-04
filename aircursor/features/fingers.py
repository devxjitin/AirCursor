"""Which fingers are extended, from a single hand's landmarks."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from aircursor.tracking.landmarks import Hand, Landmark

L = Landmark


@dataclass(frozen=True)
class FingerStates:
    thumb: bool
    index: bool
    middle: bool
    ring: bool
    pinky: bool

    @property
    def count_non_thumb(self) -> int:
        return sum((self.index, self.middle, self.ring, self.pinky))


def _dist(hand: Hand, a: int, b: int) -> float:
    return float(np.linalg.norm(hand.points[a, :2] - hand.points[b, :2]))


def _extended(hand: Hand, pip: int, tip: int) -> bool:
    # A finger is extended when its tip is farther from the wrist than its middle joint.
    # Distance-based, so it works at any hand rotation or size.
    return _dist(hand, tip, L.WRIST) > _dist(hand, pip, L.WRIST)


def finger_states(hand: Hand) -> FingerStates:
    """Classify each finger as extended (``True``) or curled (``False``)."""
    # Thumb folds sideways across the palm, so compare against the far side of the palm.
    thumb = _dist(hand, L.THUMB_TIP, L.PINKY_MCP) > _dist(hand, L.THUMB_IP, L.PINKY_MCP)
    return FingerStates(
        thumb=thumb,
        index=_extended(hand, L.INDEX_PIP, L.INDEX_TIP),
        middle=_extended(hand, L.MIDDLE_PIP, L.MIDDLE_TIP),
        ring=_extended(hand, L.RING_PIP, L.RING_TIP),
        pinky=_extended(hand, L.PINKY_PIP, L.PINKY_TIP),
    )
