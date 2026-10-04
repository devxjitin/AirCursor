"""Ties pose recognition, cursor mapping, click/drag/scroll detection and the OS backend."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from aircursor.actions.backend import InputBackend
from aircursor.cursor.mapper import DEFAULT_REGION, ActiveRegion, CursorMapper
from aircursor.features.fingers import finger_states
from aircursor.features.pinch import (
    PinchDetector,
    hand_scale,
    index_reach,
    middle_reach,
    pinch_ratio,
)
from aircursor.gestures.click import ClickDetector, ClickKind
from aircursor.gestures.pose import Pose, PoseDebouncer, classify
from aircursor.gestures.scroll import ScrollTracker
from aircursor.tracking.landmarks import Hand, Landmark

_POINTER_POSES = (Pose.POINT, Pose.PINCH)
_MIN_PINCH_REACH = 0.95  # fingertip must be out past its knuckle to start a pinch...
_CURLED_REACH = 0.85  # ...and a pinch ends if the finger curls in below this

Pos = tuple[int, int]


@dataclass(frozen=True)
class ControllerState:
    pose: Pose  # debounced pose
    cursor: Pos | None  # position sent to the OS this frame, if moving
    moving: bool
    pinched: bool = False
    click: ClickKind | None = None  # left-button event this frame (click / double / drag)
    click_pos: Pos | None = None
    right_click: bool = False
    scrolled: tuple[int, int] | None = None  # (dx, dy) wheel units sent this frame
    dragging: bool = False


class CursorController:
    """Turns hand tracking into mouse input.

    * Index finger out: cursor follows the fingertip.
    * Thumb + index pinch, released quickly: left click (twice quickly: double click).
    * Thumb + index pinch held > 0.5 s: drag (button held, cursor follows until you release).
    * Thumb + middle pinch, released quickly: right click.
    * Index + middle fingers out: scroll by moving the hand.
    * Anything else, or no hand: nothing happens.

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
        invert_scroll: bool = False,
    ) -> None:
        self._backend = backend
        w, h = backend.screen_size()
        self.mapper = CursorMapper(w, h, region)
        self._debouncer = PoseDebouncer(debounce_frames)
        self._pinch = PinchDetector()  # thumb + index
        self._rpinch = PinchDetector()  # thumb + middle
        self._left = ClickDetector(allow_drag=True)
        self._right = ClickDetector(double_window=0.0)
        self._scroll = ScrollTracker(invert=invert_scroll)
        self._lookback = lookback
        self._release_lock = release_lock
        self._history: deque[tuple[float, Pos]] = deque()
        self._was_moving = False
        self._anchor: Pos | None = None
        self._lock_until = 0.0
        self._last_click_pos: Pos | None = None
        self._last_click_t = -1e9
        self._drag_offset: Pos | None = None

    # -- helpers ---------------------------------------------------------------------------

    def _anchor_at(self, t: float) -> Pos | None:
        """Cursor position at the latest history entry not newer than ``t``."""
        found = self._history[0][1] if self._history else None
        for ts, pos in self._history:
            if ts > t:
                break
            found = pos
        return found

    def release_all(self) -> None:
        """Let go of any held mouse button. Call on shutdown."""
        if self._left.reset() is ClickKind.DRAG_END:
            self._backend.button_up("left")
        self._right.reset()

    # -- main loop -------------------------------------------------------------------------

    def update(self, hand: Hand | None, timestamp_ms: int) -> ControllerState:
        t = timestamp_ms / 1000.0

        # 1. Pinch detection (index = left button, middle = right button).
        if hand is not None:
            f = finger_states(hand)
            # Index and middle fingertips sit close together, so the thumb is often near both;
            # whichever fingertip it is nearer to wins.
            ratio_i = pinch_ratio(hand)
            ratio_m = pinch_ratio(hand, Landmark.MIDDLE_TIP)
            reach_i, reach_m = index_reach(hand), middle_reach(hand)
            left_pinched = self._pinch.update(
                ratio_i,
                reach_i >= _MIN_PINCH_REACH and ratio_i <= ratio_m and not self._rpinch.pinched,
                force_open=reach_i < _CURLED_REACH,
            )
            right_pinched = self._rpinch.update(
                ratio_m,
                reach_m >= _MIN_PINCH_REACH and ratio_m < ratio_i and not left_pinched,
                force_open=reach_m < _CURLED_REACH,
            )
            # The index finger bends while pinching, so "pointing shape" for the left button
            # only needs the other three fingers curled; the right button needs ring + pinky.
            left_ok = not (f.middle or f.ring or f.pinky)
            right_ok = not (f.ring or f.pinky)
        else:
            left_pinched = self._pinch.update(1.0)
            right_pinched = self._rpinch.update(1.0)
            left_ok = right_ok = False

        raw = classify(hand, left_pinched)
        pose = self._debouncer.update(raw)

        # 2. Click / drag state machines.
        was_held = self._left.held or self._right.held
        left_event = self._left.update(t, left_pinched, left_ok)
        right_event = self._right.update(t, right_pinched, right_ok)
        held = self._left.held or self._right.held

        if held and not was_held:  # a pinch just closed: rewind to before the approach motion
            self._anchor = self._anchor_at(t - self._lookback)
            if self._anchor is not None:
                self._backend.move_to(*self._anchor)

        click_pos: Pos | None = None
        right_click = False
        if left_event in (ClickKind.SINGLE, ClickKind.DOUBLE):
            click_pos = self._anchor
            if (
                left_event is ClickKind.DOUBLE
                and self._last_click_pos is not None
                and t - self._last_click_t <= self._left.double_window * 2
            ):
                click_pos = self._last_click_pos  # same spot, so the OS sees a double click
            if click_pos is not None:
                self._backend.click(*click_pos)
                self._last_click_pos, self._last_click_t = click_pos, t
            self._lock_until = t + self._release_lock
        elif left_event is ClickKind.DRAG_START:
            self._backend.button_down("left")
            self._drag_offset = None
        elif left_event is ClickKind.DRAG_END:
            self._backend.button_up("left")
            self._lock_until = t + self._release_lock
        if right_event is ClickKind.SINGLE and self._anchor is not None:
            self._backend.click(*self._anchor, button="right")
            right_click = True
            self._lock_until = t + self._release_lock
        if not held:
            self._anchor = None

        # 3. Cursor movement.
        dragging = self._left.dragging
        pointing = (
            pose in _POINTER_POSES
            and raw in _POINTER_POSES
            and not held
            and not left_pinched
            and not right_pinched
        )
        moving = hand is not None and t >= self._lock_until and (pointing or dragging)
        cursor: Pos | None = None
        if moving:
            assert hand is not None
            if not self._was_moving:
                self.mapper.reset()  # don't glide from where the finger was before the pause
            tip = hand.points[Landmark.INDEX_TIP]
            cursor = self.mapper.map(float(tip[0]), float(tip[1]), t)
            if dragging:
                # Start the drag from the cursor's current spot instead of jumping to the finger.
                if self._drag_offset is None and self._anchor is not None:
                    self._drag_offset = (
                        self._anchor[0] - cursor[0],
                        self._anchor[1] - cursor[1],
                    )
                off = self._drag_offset or (0, 0)
                w, h = self.mapper.screen_w, self.mapper.screen_h
                cursor = (
                    min(max(cursor[0] + off[0], 0), w - 1),
                    min(max(cursor[1] + off[1], 0), h - 1),
                )
            self._backend.move_to(*cursor)
            if not dragging:
                self._history.append((t, cursor))
                while self._history and self._history[0][0] < t - 1.0:
                    self._history.popleft()
        elif hand is None:
            self._history.clear()
        self._was_moving = moving

        # 4. Scrolling.
        scrolled: tuple[int, int] | None = None
        if hand is not None and pose is Pose.TWO_FINGERS and raw is Pose.TWO_FINGERS:
            pts = hand.points
            x = float((pts[Landmark.INDEX_TIP, 0] + pts[Landmark.MIDDLE_TIP, 0]) / 2)
            y = float((pts[Landmark.INDEX_TIP, 1] + pts[Landmark.MIDDLE_TIP, 1]) / 2)
            dx, dy = self._scroll.update(t, x, y, hand_scale(hand))
            if dx or dy:
                self._backend.scroll(dx, dy)
                scrolled = (dx, dy)
        else:
            self._scroll.reset()

        return ControllerState(
            pose,
            cursor,
            moving,
            left_pinched,
            left_event,
            click_pos,
            right_click,
            scrolled,
            dragging,
        )
