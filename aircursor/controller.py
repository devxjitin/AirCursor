"""Ties pose recognition, cursor mapping and the OS backend together."""

from __future__ import annotations

from dataclasses import dataclass

from aircursor.actions.backend import InputBackend
from aircursor.cursor.mapper import DEFAULT_REGION, ActiveRegion, CursorMapper
from aircursor.gestures.pose import Pose, PoseDebouncer, classify
from aircursor.tracking.landmarks import Hand, Landmark


@dataclass(frozen=True)
class ControllerState:
    pose: Pose  # debounced pose
    cursor: tuple[int, int] | None  # last position sent to the OS, if moving this frame
    moving: bool


class CursorController:
    """Moves the cursor with the index fingertip while the POINT pose is held.

    Any other pose, or losing the hand, freezes the cursor.
    """

    def __init__(
        self,
        backend: InputBackend,
        region: ActiveRegion = DEFAULT_REGION,
        debounce_frames: int = 3,
    ) -> None:
        self._backend = backend
        w, h = backend.screen_size()
        self.mapper = CursorMapper(w, h, region)
        self._debouncer = PoseDebouncer(debounce_frames)
        self._was_moving = False

    def update(self, hand: Hand | None, timestamp_ms: int) -> ControllerState:
        raw = classify(hand)
        pose = self._debouncer.update(raw)
        # Require the *current* frame to be POINT too, so the cursor stops the instant the
        # hand changes shape rather than after the debounce window.
        moving = pose is Pose.POINT and raw is Pose.POINT and hand is not None
        cursor = None
        if moving:
            assert hand is not None
            if not self._was_moving:
                self.mapper.reset()  # don't glide from where the finger was before the pause
            tip = hand.points[Landmark.INDEX_TIP]
            cursor = self.mapper.map(float(tip[0]), float(tip[1]), timestamp_ms / 1000.0)
            self._backend.move_to(*cursor)
        self._was_moving = moving
        return ControllerState(pose=pose, cursor=cursor, moving=moving)
