from helpers import PALM, POINT, make_hand

from aircursor.actions.backend import RecordingBackend
from aircursor.controller import CursorController
from aircursor.cursor.mapper import ActiveRegion
from aircursor.features.pinch import PinchDetector, pinch_ratio
from aircursor.gestures.click import ClickDetector, ClickKind
from aircursor.gestures.pose import Pose, classify

FRAME = 0.033


def test_pinch_ratio_open_and_closed():
    assert pinch_ratio(make_hand(**POINT, thumb=True)) > 0.8
    assert pinch_ratio(make_hand(**POINT, pinch=True)) < 0.2


def test_pinch_detector_hysteresis():
    d = PinchDetector(close_below=0.3, open_above=0.5)
    assert not d.update(0.4)
    assert d.update(0.25)
    assert d.update(0.4)  # between thresholds: stays pinched
    assert not d.update(0.6)
    assert not d.update(0.4)  # and stays open


def test_pinch_pose_overrides_bent_index():
    hand = make_hand(**POINT, pinch=True)
    assert classify(hand, pinched=True) is Pose.PINCH
    assert classify(make_hand(**PALM, pinch=True), pinched=True) is Pose.OPEN_PALM


def run(det, script, dt=FRAME):
    """script: list of (pinched, active); returns list of (frame, kind) events."""
    return [(i, k) for i, (p, a) in enumerate(script) if (k := det.update(i * dt, p, a))]


def test_quick_pinch_release_is_single_click():
    ev = run(ClickDetector(), [(False, True)] * 3 + [(True, True)] * 4 + [(False, True)] * 3)
    assert ev == [(7, ClickKind.SINGLE)]


def test_two_quick_taps_make_double():
    tap = [(True, True)] * 3 + [(False, True)] * 3
    ev = run(ClickDetector(), tap + tap)
    assert [k for _, k in ev] == [ClickKind.SINGLE, ClickKind.DOUBLE]


def test_slow_second_tap_is_single_again():
    tap = [(True, True)] * 3 + [(False, True)] * 3
    ev = run(ClickDetector(), tap + [(False, True)] * 20 + tap)
    assert [k for _, k in ev] == [ClickKind.SINGLE, ClickKind.SINGLE]


def test_third_tap_starts_over():
    tap = [(True, True)] * 3 + [(False, True)] * 3
    ev = run(ClickDetector(), tap * 3)
    assert [k for _, k in ev] == [ClickKind.SINGLE, ClickKind.DOUBLE, ClickKind.SINGLE]


def test_long_hold_is_not_a_click():
    assert run(ClickDetector(), [(True, True)] * 30 + [(False, True)] * 3) == []


def test_one_frame_blip_is_ignored():
    assert run(ClickDetector(), [(False, True), (True, True), (False, True)] * 2) == []


def test_losing_hand_while_pinched_cancels_and_requires_reopen():
    det = ClickDetector()
    script = [(True, True)] * 3 + [(True, False)] * 2 + [(True, True)] * 3 + [(False, True)] * 2
    assert run(det, script) == []  # pinch was never re-armed after the cancel


# --- controller integration -------------------------------------------------------------


def drive(ctrl, hand, frames, start):
    out = []
    for i in range(frames):
        out.append(ctrl.update(hand, round((start + i) * FRAME * 1000)))
    return out, start + frames


def make_ctrl():
    be = RecordingBackend(1000, 1000)
    return be, CursorController(be, region=ActiveRegion(0, 0, 1, 1))


def test_pinch_and_release_clicks_once():
    be, ctrl = make_ctrl()
    _, n = drive(ctrl, make_hand(**POINT), 10, 0)
    _, n = drive(ctrl, make_hand(**POINT, pinch=True), 5, n)
    states, n = drive(ctrl, make_hand(**POINT), 6, n)
    assert len(be.clicks) == 1
    assert [s.click for s in states if s.click] == [ClickKind.SINGLE]


def test_cursor_frozen_while_pinched():
    be, ctrl = make_ctrl()
    _, n = drive(ctrl, make_hand(**POINT), 10, 0)
    moves_before = len(be.moves)
    drive(ctrl, make_hand(**POINT, pinch=True, offset=(0.1, 0.0)), 8, n)
    # one snap-back move to the anchor, then nothing while the pinch is held
    assert len(be.moves) - moves_before == 1


def test_click_lands_where_cursor_was_before_the_approach():
    be, ctrl = make_ctrl()
    _, n = drive(ctrl, make_hand(**POINT), 15, 0)
    before = be.moves[-1]
    # the finger drifts toward the thumb for 3 frames, then the pinch closes
    for dx in (0.02, 0.04, 0.06):
        _, n = drive(ctrl, make_hand(**POINT, offset=(dx, 0.02)), 1, n)
    _, n = drive(ctrl, make_hand(**POINT, pinch=True, offset=(0.06, 0.02)), 5, n)
    drive(ctrl, make_hand(**POINT), 6, n)
    assert be.clicks == [before]


def test_double_tap_clicks_twice_at_the_same_spot():
    be, ctrl = make_ctrl()
    _, n = drive(ctrl, make_hand(**POINT), 15, 0)
    for _ in range(2):
        _, n = drive(ctrl, make_hand(**POINT, pinch=True), 3, n)
        _, n = drive(ctrl, make_hand(**POINT), 3, n)
    assert len(be.clicks) == 2 and be.clicks[0] == be.clicks[1]


def test_no_click_when_open_palm_pinch():
    be, ctrl = make_ctrl()
    drive(ctrl, make_hand(**PALM, pinch=True), 5, 0)
    drive(ctrl, make_hand(**PALM), 5, 5)
    assert be.clicks == []


def test_cursor_resumes_after_click():
    be, ctrl = make_ctrl()
    _, n = drive(ctrl, make_hand(**POINT), 10, 0)
    _, n = drive(ctrl, make_hand(**POINT, pinch=True), 4, n)
    _, n = drive(ctrl, make_hand(**POINT), 3, n)
    moves = len(be.moves)
    drive(ctrl, make_hand(**POINT, offset=(0.2, 0.0)), 20, n)
    assert len(be.moves) > moves


def test_one_frame_pinch_does_not_click():
    be, ctrl = make_ctrl()
    _, n = drive(ctrl, make_hand(**POINT), 10, 0)
    _, n = drive(ctrl, make_hand(**POINT, pinch=True), 1, n)
    drive(ctrl, make_hand(**POINT), 5, n)
    assert be.clicks == []


def test_fist_with_tucked_thumb_is_not_a_pinch():
    be, ctrl = make_ctrl()
    _, n = drive(ctrl, make_hand(), 5, 0)
    states, n = drive(ctrl, make_hand(), 5, n)
    drive(ctrl, make_hand(**POINT), 5, n)
    assert not any(s.pinched for s in states) and be.clicks == []


def test_pinch_force_open_releases_even_when_thumb_still_close():
    d = PinchDetector()
    assert d.update(0.1)
    assert d.update(0.1)
    assert not d.update(0.1, force_open=True)
