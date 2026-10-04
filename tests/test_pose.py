import pytest
from helpers import FIST, PALM, POINT, TWO, make_hand

from aircursor.features.fingers import finger_states
from aircursor.gestures.pose import Pose, PoseDebouncer, classify


def test_finger_states_point():
    f = finger_states(make_hand(**POINT))
    assert (f.thumb, f.index, f.middle, f.ring, f.pinky) == (False, True, False, False, False)


def test_finger_states_thumb_out():
    assert finger_states(make_hand(thumb=True)).thumb


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (POINT, Pose.POINT),
        (dict(index=True, thumb=True), Pose.POINT),  # thumb ignored
        (TWO, Pose.TWO_FINGERS),
        (PALM, Pose.OPEN_PALM),
        (FIST, Pose.FIST),
        (dict(thumb=True), Pose.FIST),
        (dict(index=True, ring=True), Pose.OTHER),
        (dict(pinky=True), Pose.OTHER),
    ],
)
def test_classify(kwargs, expected):
    assert classify(make_hand(**kwargs)) is expected


def test_classify_none():
    assert classify(None) is Pose.NONE


def test_debouncer_needs_consecutive_frames():
    d = PoseDebouncer(frames=3)
    assert d.update(Pose.POINT) is Pose.NONE
    assert d.update(Pose.POINT) is Pose.NONE
    assert d.update(Pose.POINT) is Pose.POINT


def test_debouncer_ignores_flicker():
    d = PoseDebouncer(frames=3, initial=Pose.POINT)
    for raw in (Pose.FIST, Pose.POINT, Pose.FIST, Pose.POINT, Pose.OTHER):
        assert d.update(raw) is Pose.POINT


def test_debouncer_single_frame_mode():
    assert PoseDebouncer(frames=1).update(Pose.FIST) is Pose.FIST
