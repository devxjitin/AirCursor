import pytest
from helpers import FIST, PALM, POINT, make_hand

from aircursor.actions.backend import RecordingBackend
from aircursor.controller import CursorController
from aircursor.cursor.mapper import ActiveRegion, CursorMapper
from aircursor.cursor.one_euro import OneEuroFilter
from aircursor.gestures.pose import Pose


def test_one_euro_passes_first_sample_and_converges():
    f = OneEuroFilter(min_cutoff=1.0)
    assert f(5.0, 0.0) == 5.0
    y = 5.0
    for i in range(1, 200):
        y = f(10.0, i * 0.033)
    assert y == pytest.approx(10.0, abs=0.01)


def test_one_euro_smooths_jitter_when_still():
    f = OneEuroFilter(min_cutoff=1.0, beta=0.0)
    f(0.0, 0.0)
    out = [f(0.01 * (-1) ** i, i * 0.033) for i in range(1, 60)]
    assert max(abs(v) for v in out) < 0.005


def test_one_euro_lags_less_when_fast():
    slow = OneEuroFilter(min_cutoff=1.0, beta=0.0)
    fast = OneEuroFilter(min_cutoff=1.0, beta=10.0)
    for flt in (slow, fast):
        flt(0.0, 0.0)
    a = b = 0.0
    for i in range(1, 6):
        a, b = slow(i * 0.2, i * 0.033), fast(i * 0.2, i * 0.033)
    assert b > a


def test_region_clamps():
    r = ActiveRegion(0.2, 0.2, 0.8, 0.8)
    assert r.to_unit(0.5, 0.5) == pytest.approx((0.5, 0.5))
    assert r.to_unit(0.0, 1.0) == (0.0, 1.0)


def test_mapper_mirrors_x():
    m = CursorMapper(1000, 500, ActiveRegion(0.0, 0.0, 1.0, 1.0), mirror=True)
    x, y = m.map(0.1, 0.5, 0.0)  # hand on image-left == user's right in a mirror
    assert x == pytest.approx(899, abs=1) and y == pytest.approx(250, abs=1)


def test_mapper_reaches_screen_corners():
    m = CursorMapper(1920, 1080, ActiveRegion(0.2, 0.2, 0.8, 0.8), mirror=False)
    assert m.map(0.0, 0.0, 0.0) == (0, 0)
    m.reset()
    assert m.map(1.0, 1.0, 1.0) == (1919, 1079)


def _drive(ctrl, hand, frames, t0=0):
    out = None
    for i in range(frames):
        out = ctrl.update(hand, t0 + i * 33)
    return out


def test_controller_moves_only_in_point_pose():
    be = RecordingBackend(1000, 1000)
    ctrl = CursorController(be)
    _drive(ctrl, make_hand(**POINT), 10)
    assert be.moves, "should move once POINT is stable"
    n = len(be.moves)
    state = _drive(ctrl, make_hand(**PALM), 10, t0=1000)
    assert state.pose is Pose.OPEN_PALM and not state.moving
    assert len(be.moves) == n  # frozen on open palm


def test_controller_freezes_when_hand_lost():
    be = RecordingBackend()
    ctrl = CursorController(be)
    _drive(ctrl, make_hand(**POINT), 10)
    n = len(be.moves)
    state = _drive(ctrl, None, 10, t0=1000)
    assert state.pose is Pose.NONE and len(be.moves) == n


def test_controller_ignores_fist_and_short_flicker():
    be = RecordingBackend()
    ctrl = CursorController(be)
    _drive(ctrl, make_hand(**FIST), 10)
    assert be.moves == []
    _drive(ctrl, make_hand(**POINT), 2)  # shorter than the debounce window
    assert be.moves == []


def test_controller_follows_finger_direction():
    be = RecordingBackend(1000, 1000)
    ctrl = CursorController(be, region=ActiveRegion(0, 0, 1, 1))
    _drive(ctrl, make_hand(**POINT), 5)
    left = be.moves[-1]
    _drive(ctrl, make_hand(**POINT, offset=(0.2, 0.0)), 60, t0=1000)
    # hand moved to image-right => cursor moves to screen-left in mirrored mapping
    assert be.moves[-1][0] < left[0]


def test_resume_after_pause_does_not_glide():
    be = RecordingBackend(1000, 1000)
    ctrl = CursorController(be, region=ActiveRegion(0, 0, 1, 1))
    _drive(ctrl, make_hand(**POINT), 5)
    _drive(ctrl, make_hand(**PALM), 5, t0=500)
    be.moves.clear()
    far = make_hand(**POINT, offset=(0.25, 0.0))
    _drive(ctrl, far, 3, t0=1000)
    # first move after the pause lands where the finger actually is (filter was reset)
    expected = CursorMapper(1000, 1000, ActiveRegion(0, 0, 1, 1)).map(
        float(far.points[8][0]), float(far.points[8][1]), 0.0
    )
    assert be.moves[0] == expected
