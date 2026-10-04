import json

import pytest
from helpers import POINT, make_hand

from aircursor import config as cfgmod
from aircursor.actions.backend import RecordingBackend
from aircursor.cli import main, replay
from aircursor.config import Config
from aircursor.controller import CursorController
from aircursor.gestures.pose import Pose, classify
from aircursor.gestures.scroll import ScrollTracker
from aircursor.recording import frame_to_json, read_frames, write_frame

FRAME = 0.033
THREE = dict(index=True, middle=True, ring=True)
TWO = dict(index=True, middle=True)


# --- pose ----------------------------------------------------------------------------------


def test_three_fingers_pose():
    assert classify(make_hand(**THREE)) is Pose.THREE_FINGERS
    assert classify(make_hand(**TWO)) is Pose.TWO_FINGERS
    assert classify(make_hand(index=True, ring=True, pinky=True)) is Pose.OTHER


# --- inertia (tracker level) ---------------------------------------------------------------


def flick(tr, n=12, step=0.02, start=0.7):
    t = 0.0
    for i in range(n):
        t = i * FRAME
        tr.update(t, 0.5, start - step * i, 0.3)
    return t


def drain(tr, t, frames=200):
    out = []
    for _ in range(frames):
        t += FRAME
        out.append(tr.coast(t)[1])
        if not tr.coasting:
            break
    return out


def test_flick_then_stop_glides_and_decays_to_zero():
    tr = ScrollTracker()
    t = flick(tr)
    tr.stop(coast=True)
    assert tr.coasting
    out = drain(tr, t)
    assert sum(out) > 0
    assert not tr.coasting
    early, late = sum(out[:5]), sum(out[-5:])
    assert early > late  # fading out


def test_no_coast_without_flag_or_when_hand_was_still():
    tr = ScrollTracker()
    flick(tr)
    tr.stop(coast=False)
    assert not tr.coasting
    tr = ScrollTracker()
    t = flick(tr)
    for i in range(1, 14):  # hold perfectly still for ~430 ms
        tr.update(t + i * FRAME, 0.5, 0.5 - 0.02 * 11, 0.3)
    tr.stop(coast=True)
    assert not tr.coasting


def test_slow_drift_does_not_coast():
    tr = ScrollTracker()
    flick(tr, step=0.002)
    tr.stop(coast=True)
    assert not tr.coasting


def test_coast_direction_matches_flick_direction():
    tr = ScrollTracker()
    t = flick(tr, start=0.3, step=-0.02)  # hand moving down
    tr.stop(coast=True)
    assert sum(drain(tr, t)) < 0


def test_cancel_coast_stops_immediately():
    tr = ScrollTracker()
    t = flick(tr)
    tr.stop(coast=True)
    tr.cancel_coast()
    assert not tr.coasting and tr.coast(t + FRAME) == (0, 0)


def test_vertical_only_ignores_horizontal_motion():
    tr = ScrollTracker(vertical_only=True)
    out = [tr.update(i * FRAME, 0.7 - 0.02 * i, 0.5, 0.3) for i in range(20)]
    assert sum(abs(o[0]) + abs(o[1]) for o in out) == 0


# --- controller: inertia, zoom -------------------------------------------------------------


def make_ctrl(**scroll):
    be = RecordingBackend(1000, 1000)
    cfg = Config()
    cfg.cursor.region = [0.0, 0.0, 1.0, 1.0]
    for k, v in scroll.items():
        setattr(cfg.scroll, k, v)
    return be, CursorController(be, config=cfg)


def drive(ctrl, hand, frames, start):
    out = []
    for i in range(frames):
        out.append(ctrl.update(hand, round((start + i) * FRAME * 1000)))
    return out, start + frames


def swipe(ctrl, pose, n, start, step=0.02):
    for i in range(n):
        drive(ctrl, make_hand(**pose, offset=(0.0, -step * i)), 1, start + i)
    return start + n


def test_flick_keeps_scrolling_after_fingers_drop():
    be, ctrl = make_ctrl()
    _, n = drive(ctrl, make_hand(**TWO), 6, 0)
    n = swipe(ctrl, TWO, 15, n)
    during = len(be.scrolls)
    drive(ctrl, make_hand(), 40, n)  # fist/closed hand: not scrolling any more
    assert len(be.scrolls) > during
    assert all(dy >= 0 for _, dy in be.scrolls)


def test_inertia_can_be_turned_off():
    be, ctrl = make_ctrl(inertia=False)
    _, n = drive(ctrl, make_hand(**TWO), 6, 0)
    n = swipe(ctrl, TWO, 15, n)
    during = len(be.scrolls)
    drive(ctrl, make_hand(), 40, n)
    assert len(be.scrolls) == during


def test_pinch_stops_a_glide():
    be, ctrl = make_ctrl()
    _, n = drive(ctrl, make_hand(**TWO), 6, 0)
    n = swipe(ctrl, TWO, 15, n)
    drive(ctrl, make_hand(), 3, n)
    n += 3
    drive(ctrl, make_hand(**POINT, pinch=True), 2, n)
    count = len(be.scrolls)
    drive(ctrl, make_hand(**POINT, pinch=True), 30, n + 2)
    assert len(be.scrolls) == count


def test_three_finger_swipe_zooms_not_scrolls():
    be, ctrl = make_ctrl()
    _, n = drive(ctrl, make_hand(**THREE), 6, 0)
    swipe(ctrl, THREE, 15, n)
    assert sum(be.zooms) > 0 and be.scrolls == []


def test_three_finger_swipe_down_zooms_out():
    be, ctrl = make_ctrl()
    _, n = drive(ctrl, make_hand(**THREE), 6, 0)
    swipe(ctrl, THREE, 15, n, step=-0.02)
    assert sum(be.zooms) < 0


def test_zoom_can_be_disabled():
    be, ctrl = make_ctrl()
    ctrl._zoom_enabled = False
    _, n = drive(ctrl, make_hand(**THREE), 6, 0)
    swipe(ctrl, THREE, 15, n)
    assert be.zooms == []


def test_moving_hand_during_right_click_pinch_does_not_scroll():
    be, ctrl = make_ctrl()
    _, n = drive(ctrl, make_hand(**POINT), 10, 0)
    for i in range(15):
        hand = make_hand(index=True, middle=True, pinch_middle=True, offset=(0.0, -0.02 * i))
        drive(ctrl, hand, 1, n + i)
    assert be.scrolls == [] and be.zooms == []


# --- config --------------------------------------------------------------------------------


def test_new_config_keys_round_trip_and_validate(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text(
        "[scroll]\ninertia = false\ninertia_time = 0.8\n[zoom]\nenabled = false\ngain = 200\n"
    )
    cfg = cfgmod.load(p)
    assert not cfg.scroll.inertia and cfg.scroll.inertia_time == 0.8
    assert not cfg.zoom.enabled and cfg.zoom.gain == 200.0
    assert cfgmod.load(cfgmod.save(cfg, tmp_path / "d.toml")) == cfg
    p.write_text("[zoom]\ngain = 0\n")
    with pytest.raises(cfgmod.ConfigError):
        cfgmod.load(p)


# --- record / replay -----------------------------------------------------------------------


def test_recording_round_trip(tmp_path):
    path = tmp_path / "r.jsonl"
    hands = [None, make_hand(**POINT), make_hand(**TWO, offset=(0.1, 0.0))]
    with open(path, "w", encoding="utf-8") as fp:
        for i, h in enumerate(hands):
            write_frame(fp, i * 33, h)
    got = list(read_frames(path))
    assert [t for t, _ in got] == [0, 33, 66]
    assert got[0][1] is None
    assert got[2][1].points == pytest.approx(hands[2].points, abs=1e-4)
    assert got[1][1].handedness == "Right"


def test_bad_recording_line_names_the_line(tmp_path):
    path = tmp_path / "r.jsonl"
    path.write_text(frame_to_json(0, None) + "\n" + json.dumps({"t": 1}) + "\n")
    with pytest.raises(ValueError, match=r":2:"):
        list(read_frames(path))


def click_sequence():
    point, pinch = make_hand(**POINT), make_hand(**POINT, pinch=True)
    return [point] * 15 + [pinch] * 4 + [point] * 5


def test_replay_reproduces_a_click_and_never_touches_the_os(tmp_path):
    path = tmp_path / "r.jsonl"
    seq = (
        [make_hand(**POINT)] * 15 + [make_hand(**POINT, pinch=True)] * 4 + [make_hand(**POINT)] * 5
    )
    with open(path, "w", encoding="utf-8") as fp:
        for i, h in enumerate(seq):
            write_frame(fp, round(i * 33), h)
    events = replay(path, CursorController(RecordingBackend()))
    assert [label for _, label in events] == ["CLICK"]


def test_cli_replay_prints_events(tmp_path, capsys):
    path = tmp_path / "r.jsonl"
    seq = (
        [make_hand(**POINT)] * 15 + [make_hand(**POINT, pinch=True)] * 4 + [make_hand(**POINT)] * 5
    )
    with open(path, "w", encoding="utf-8") as fp:
        for i, h in enumerate(seq):
            write_frame(fp, round(i * 33), h)
    assert main(["replay", str(path)]) == 0
    out = capsys.readouterr().out
    assert "CLICK" in out and "1 events" in out
