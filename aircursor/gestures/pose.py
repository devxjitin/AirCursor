"""Static hand poses and a debouncer that makes pose changes stable."""

from __future__ import annotations

from enum import Enum

from aircursor.features.fingers import FingerStates, finger_states
from aircursor.tracking.landmarks import Hand


class Pose(Enum):
    NONE = "none"  # no hand in view
    POINT = "point"  # index only: move the cursor
    TWO_FINGERS = "two_fingers"  # index + middle: scroll (later phase)
    OPEN_PALM = "open_palm"  # pause
    FIST = "fist"  # idle / lock
    OTHER = "other"  # anything else


def classify_fingers(f: FingerStates) -> Pose:
    # The thumb is ignored for the main poses: people hold it in or out unpredictably.
    if f.count_non_thumb == 4:
        return Pose.OPEN_PALM
    if f.count_non_thumb == 0:
        return Pose.FIST
    if f.index and not (f.middle or f.ring or f.pinky):
        return Pose.POINT
    if f.index and f.middle and not (f.ring or f.pinky):
        return Pose.TWO_FINGERS
    return Pose.OTHER


def classify(hand: Hand | None) -> Pose:
    return Pose.NONE if hand is None else classify_fingers(finger_states(hand))


class PoseDebouncer:
    """Only switch the stable pose after a new pose has been seen for ``frames`` in a row."""

    def __init__(self, frames: int = 3, initial: Pose = Pose.NONE) -> None:
        self._frames = frames
        self.stable = initial
        self._candidate = initial
        self._count = 0

    def update(self, raw: Pose) -> Pose:
        if raw == self.stable:
            self._candidate, self._count = raw, 0
        elif raw == self._candidate:
            self._count += 1
            if self._count >= self._frames:
                self.stable, self._count = raw, 0
        else:
            self._candidate, self._count = raw, 1
            if self._frames <= 1:
                self.stable, self._count = raw, 0
        return self.stable
