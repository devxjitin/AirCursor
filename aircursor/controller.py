"""Ties pose recognition, cursor mapping, click detection and the OS backend together."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from aircursor.actions.backend import InputBackend
from aircursor.cursor.mapper import DEFAULT_REGION, ActiveRegion, CursorMapper
from aircursor.features.fingers import finger_states
from aircursor.features.pinch import PinchDetector, index_reach, pinch_ratio
from aircursor.gestures.click import ClickDetector, ClickKind
from aircursor.gestures.pose import Pose, PoseDebouncer, classify
from aircursor.tracking.landmarks import Hand, Landmark

_POINTER_POSES = (Pose.POINT, Pose.PINCH)
_MIN_PINCH_REACH = 0.95


@dataclass(frozen=True)
class ControllerState:
    pose: Pose  # debounced pose
    cursor: tuple[int, int] | None  # position sent to the OS this frame, if moving
    moving: bool
    pinched: bool = False
    click: ClickKind | None = None
    click_pos: tuple[int, int] | None = None


class CursorController:
    """Moves the cursor with the index fingertip and clicks on a thumb-index pinch.

    Any non-pointing pose, or losing the hand, freezes the cursor.

    Pinching drags the fingertip, so a naive implementation clicks in the wrong place.
    We keep a short history of cursor positions; when a pinch closes we snap back to where
    the cursor was ``lookback`` seconds earlier (before the approach motion) and hold it
    there until shortly after release.
    """

    def __init__(
        self,
        backend: InputBackend,
        region: ActiveRegion = DEFAULT_REGION,
        debounce_frames: int = 3,
        lookback: float = 0.20,
        release_lock: float = 0.15,
    ) -> None:
        self._backend = backend
        w, h = backend.screen_size()
        self.mapper = CursorMapper(w, h, region)
        self._debouncer = PoseDebouncer(debounce_frames)
        self._pinch = PinchDetector()
        self._clicks = ClickDetector()
        self._lookback = lookback
        self._release_lock = release_lock
        self._history: deque[tuple[float, tuple[int, int]]] = deque()
        self._was_moving = False
        self._anchor: tuple[int, int] | None = None
        self._lock_until = 0.0
        self._last_click_pos: tuple[int, int] | None = None
        self._last_click_t = -1e9

    def _anchor_at(self, t: float) -> tuple[int, int] | None:
        """Cursor position at the latest history entry not newer than ``t``."""
        found = self._history[0][1] if self._history else None
        for ts, pos in self._history:
            if ts > t:
                break
            found = pos
        return found

    def update(self, hand: Hand | None, timestamp_ms: int) -> ControllerState:
        t = timestamp_ms / 1000.0
        if hand is not None:
            # A fist also brings thumb and index together; require the index tip to stay out
            # past its knuckle before a pinch may start.
            pinched = self._pinch.update(pinch_ratio(hand), index_reach(hand) >= _MIN_PINCH_REACH)
        else:
            pinched = self._pinch.update(1.0)
        raw = classify(hand, pinched)
        pose = self._debouncer.update(raw)

        # "Pointing shape" for click purposes only needs the other three fingers curled;
        # the index finger bends while pinching so it can't be part of the test.
        curled = False
        if hand is not None:
            f = finger_states(hand)
            curled = not (f.middle or f.ring or f.pinky)
        was_pressed = self._clicks.pressed
        kind = self._clicks.update(t, pinched, active=hand is not None and curled)

        if self._clicks.pressed and not was_pressed:  # pinch just closed
            self._anchor = self._anchor_at(t - self._lookback)
            if self._anchor is not None:
                self._backend.move_to(*self._anchor)
        click_pos = None
        if kind is not None:
            click_pos = self._anchor
            if (
                kind is ClickKind.DOUBLE
                and self._last_click_pos is not None
                and t - self._last_click_t <= self._clicks.double_window * 2
            ):
                click_pos = self._last_click_pos  # same spot, so the OS sees a double click
            if click_pos is not None:
                self._backend.click(*click_pos)
                self._last_click_pos, self._last_click_t = click_pos, t
            self._lock_until = t + self._release_lock
        if not self._clicks.pressed:
            self._anchor = None

        # Cursor follows the finger only when pointing, not mid-pinch, and not just after a click.
        moving = (
            pose in _POINTER_POSES
            and raw in _POINTER_POSES
            and hand is not None
            and not self._clicks.pressed
            and t >= self._lock_until
            and not pinched
        )
        cursor = None
        if moving:
            assert hand is not None
            if not self._was_moving:
                self.mapper.reset()  # don't glide from where the finger was before the pause
            tip = hand.points[Landmark.INDEX_TIP]
            cursor = self.mapper.map(float(tip[0]), float(tip[1]), t)
            self._backend.move_to(*cursor)
            self._history.append((t, cursor))
            while self._history and self._history[0][0] < t - 1.0:
                self._history.popleft()
        elif hand is None:
            self._history.clear()
        self._was_moving = moving
        return ControllerState(pose, cursor, moving, pinched, kind, click_pos)
