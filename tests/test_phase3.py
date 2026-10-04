from helpers import PALM, POINT, TWO, make_hand

from aircursor.actions.backend import RecordingBackend
from aircursor.controller import CursorController
from aircursor.cursor.mapper import ActiveRegion
from aircursor.gestures.click import ClickDetector, ClickKind
from aircursor.gestures.scroll import ScrollTracker

FRAME = 0.033


# --- drag state machine ------------------------------------------------------------------


def run(det, script, dt=FRAME):
    return [(i, k) for i, (p, a) in enumerate(script) if (k := det.update(i * dt, p, a))]


def test_long_hold_starts_and_release_ends_drag():
    det = ClickDetector(allow_drag=True)
    ev = run(det, [(True, True)] * 25 + [(False, True)] * 3)
    assert [k for _, k in ev] == [ClickKind.DRAG_START, ClickKind.DRAG_END]


def test_short_pinch_is_still_a_click_with_drag_enabled():
    ev = run(ClickDetector(allow_drag=True), [(True, True)] * 4 + [(False, True)] * 3)
    assert [k for _, k in ev] == [ClickKind.SINGLE]


def test_drag_survives_brief_tracking_glitch_but_ends_when_hand_lost():
    det = ClickDetector(allow_drag=True)
    glitch = [(True, True)] * 20 + [(True, False)] * 3 + [(True, True)] * 3  # ~100 ms
    assert [k for _, k in run(det, glitch)] == [ClickKind.DRAG_START]
    gone = [(True, True)] * 20 + [(False, False)] * 15
    assert [k for _, k in run(ClickDetector(allow_drag=True), gone)][-1] is ClickKind.DRAG_END


def test_reset_reports_drag_end():
    det = ClickDetector(allow_drag=True)
    run(det, [(True, True)] * 25)
    assert det.dragging and det.reset() is ClickKind.DRAG_END and not det.held


# --- scroll tracker ----------------------------------------------------------------------


def feed(tr, ys, x=0.5, scale=0.3):
    out = [tr.update(i * FRAME, x, y, scale) for i, y in enumerate(ys)]
    return sum(o[0] for o in out), sum(o[1] for o in out)


def test_scroll_up_is_positive_and_down_negative():
    ups = [0.6 - 0.02 * i for i in range(20)]
    assert feed(ScrollTracker(), ups)[1] > 0
    downs = [0.3 + 0.02 * i for i in range(20)]
    assert feed(ScrollTracker(), downs)[1] < 0


def test_invert_flips_direction():
    ups = [0.6 - 0.02 * i for i in range(20)]
    assert feed(ScrollTracker(invert=True), ups)[1] < 0


def test_still_hand_does_not_scroll():
    assert feed(ScrollTracker(), [0.5, 0.5005, 0.4995] * 10) == (0, 0)


def test_horizontal_motion_scrolls_x_only_and_mirrors():
    tr = ScrollTracker()
    out = [tr.update(i * FRAME, 0.7 - 0.02 * i, 0.5, 0.3) for i in range(20)]
    assert sum(o[0] for o in out) > 0 and sum(o[1] for o in out) == 0  # image-left = user's right


def test_faster_motion_scrolls_disproportionately_more():
    slow = feed(ScrollTracker(), [0.6 - 0.01 * i for i in range(20)])[1]
    fast = feed(ScrollTracker(), [0.6 - 0.02 * i for i in range(20)])[1]
    assert fast > 2 * slow


def test_scroll_reset_starts_fresh():
    tr = ScrollTracker()
    feed(tr, [0.6 - 0.02 * i for i in range(10)])
    tr.reset()
    assert tr.update(10.0, 0.5, 0.1, 0.3) == (0, 0)  # no jump from the previous position


# --- controller integration --------------------------------------------------------------


def make_ctrl():
    be = RecordingBackend(1000, 1000)
    return be, CursorController(be, region=ActiveRegion(0, 0, 1, 1))


def drive(ctrl, hand, frames, start):
    out = []
    for i in range(frames):
        out.append(ctrl.update(hand, round((start + i) * FRAME * 1000)))
    return out, start + frames


def test_two_finger_swipe_scrolls_and_freezes_cursor():
    be, ctrl = make_ctrl()
    _, n = drive(ctrl, make_hand(**TWO), 6, 0)
    moves = len(be.moves)
    for i in range(15):
        _, n = drive(ctrl, make_hand(**TWO, offset=(0.0, -0.02 * i)), 1, n)
    assert sum(dy for _, dy in be.scrolls) > 0
    assert len(be.moves) == moves  # cursor stays put while scrolling


def test_pointing_does_not_scroll():
    be, ctrl = make_ctrl()
    for i in range(15):
        drive(ctrl, make_hand(**POINT, offset=(0.0, -0.02 * i)), 1, i)
    assert be.scrolls == []


def test_open_palm_does_not_scroll():
    be, ctrl = make_ctrl()
    for i in range(15):
        drive(ctrl, make_hand(**PALM, offset=(0.0, -0.02 * i)), 1, i)
    assert be.scrolls == []


def test_middle_pinch_right_clicks_once_where_cursor_was():
    be, ctrl = make_ctrl()
    _, n = drive(ctrl, make_hand(**POINT), 15, 0)
    before = be.moves[-1]
    _, n = drive(ctrl, make_hand(index=True, middle=True, pinch_middle=True), 4, n)
    _, n = drive(ctrl, make_hand(**POINT), 5, n)
    assert be.right_clicks == [before] and be.clicks == []


def test_index_pinch_with_index_next_to_middle_is_left_click_not_right():
    be, ctrl = make_ctrl()
    _, n = drive(ctrl, make_hand(**POINT), 10, 0)
    _, n = drive(ctrl, make_hand(**POINT, pinch=True), 4, n)
    drive(ctrl, make_hand(**POINT), 5, n)
    assert len(be.clicks) == 1 and be.right_clicks == []


def test_long_pinch_drags_then_drops():
    be, ctrl = make_ctrl()
    _, n = drive(ctrl, make_hand(**POINT), 15, 0)
    start = be.moves[-1]
    _, n = drive(ctrl, make_hand(**POINT, pinch=True), 20, n)  # ~0.66 s hold
    assert ("down", "left") in be.button_events and be.clicks == []
    moves_at_drag = len(be.moves)
    # carry the pinched hand to the right of the image, i.e. toward screen-left (mirrored)
    for i in range(1, 25):
        states, n = drive(ctrl, make_hand(**POINT, pinch=True, offset=(0.01 * i, 0.0)), 1, n)
    assert states[-1].dragging
    assert len(be.moves) > moves_at_drag and be.moves[-1][0] < start[0]
    assert ("up", "left") not in be.button_events
    drive(ctrl, make_hand(**POINT), 4, n)
    assert be.button_events == [("down", "left"), ("up", "left")]
    assert be.clicks == []


def test_drag_starts_from_cursor_position_without_jump():
    be, ctrl = make_ctrl()
    _, n = drive(ctrl, make_hand(**POINT), 15, 0)
    start = be.moves[-1]
    # the pinch pulls the fingertip a bit; hold still through drag start
    _, n = drive(ctrl, make_hand(**POINT, pinch=True, offset=(0.03, 0.02)), 22, n)
    assert abs(be.moves[-1][0] - start[0]) <= 2 and abs(be.moves[-1][1] - start[1]) <= 2


def test_losing_hand_during_drag_releases_button():
    be, ctrl = make_ctrl()
    _, n = drive(ctrl, make_hand(**POINT), 15, 0)
    _, n = drive(ctrl, make_hand(**POINT, pinch=True), 20, n)
    drive(ctrl, None, 15, n)
    assert be.button_events[-1] == ("up", "left")


def test_release_all_lets_go_of_button():
    be, ctrl = make_ctrl()
    _, n = drive(ctrl, make_hand(**POINT), 15, 0)
    drive(ctrl, make_hand(**POINT, pinch=True), 20, n)
    ctrl.release_all()
    assert be.button_events[-1] == ("up", "left")
    ctrl.release_all()
    assert be.button_events.count(("up", "left")) == 1  # idempotent
