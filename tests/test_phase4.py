import numpy as np
import pytest
from helpers import FIST, POINT, make_hand

from aircursor import config as cfgmod
from aircursor.actions.backend import RecordingBackend
from aircursor.calibration import CalibrationSession
from aircursor.cli import main
from aircursor.config import Config, ConfigError
from aircursor.controller import CursorController
from aircursor.cursor.mapper import ActiveRegion
from aircursor.doctor import Check, run_doctor
from aircursor.tracking.landmarks import Hand
from aircursor.tracking.select import select_hand
from aircursor.ui.overlay import draw_calibration

FRAME = 0.033


# --- config --------------------------------------------------------------------------------


def test_default_config_round_trips_through_toml(tmp_path):
    path = cfgmod.save(Config(), tmp_path / "c.toml")
    assert cfgmod.load(path) == Config()


def test_partial_config_overrides_only_given_keys(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[scroll]\ninvert = true\n[hand]\npreferred = "left"\n')
    cfg = cfgmod.load(p)
    assert cfg.scroll.invert and cfg.hand.preferred == "left"
    assert cfg.scroll.gain == Config().scroll.gain


@pytest.mark.parametrize(
    "text",
    [
        "[scroll]\ngian = 3\n",  # typo'd key
        "[nonsense]\nx = 1\n",
        '[scroll]\ngain = "fast"\n',
        '[hand]\npreferred = "both"\n',
        "[cursor]\nregion = [0.5, 0.5, 0.4, 0.4]\n",
        "[cursor]\nregion = [0.1, 0.1, 0.15, 0.9]\n",  # too narrow
        "[click]\npinch_close = 0.6\npinch_open = 0.5\n",
        "this is not toml",
    ],
)
def test_invalid_config_is_rejected_with_a_message(tmp_path, text):
    p = tmp_path / "c.toml"
    p.write_text(text)
    with pytest.raises(ConfigError):
        cfgmod.load(p)


def test_missing_explicit_config_is_an_error_but_default_is_not(tmp_path, monkeypatch):
    with pytest.raises(ConfigError):
        cfgmod.load(tmp_path / "nope.toml")
    monkeypatch.setattr(cfgmod, "default_path", lambda: tmp_path / "absent.toml")
    assert cfgmod.load() == Config()


def test_integers_are_accepted_for_float_settings(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text("[scroll]\ngain = 1000\n")
    assert cfgmod.load(p).scroll.gain == 1000.0


def test_cli_config_init_show_and_no_overwrite(tmp_path, capsys):
    path = str(tmp_path / "c.toml")
    assert main(["--config", path, "config", "init"]) == 0
    assert main(["--config", path, "config", "init"]) == 1  # refuses to overwrite
    assert main(["--config", path, "config", "show"]) == 0
    assert "[scroll]" in capsys.readouterr().out


def test_cli_reports_bad_config(tmp_path, capsys):
    p = tmp_path / "c.toml"
    p.write_text("[scroll]\ngian = 3\n")
    assert main(["--config", str(p), "run", "--dry-run", "--no-window"]) == 2
    assert "Config error" in capsys.readouterr().out


def test_controller_uses_config_values():
    cfg = Config()
    cfg.cursor.region = [0.0, 0.0, 1.0, 1.0]
    cfg.click.max_hold = 0.2
    ctrl = CursorController(RecordingBackend(), config=cfg)
    assert ctrl.mapper.region == ActiveRegion(0.0, 0.0, 1.0, 1.0)
    assert ctrl._left.max_hold == 0.2


# --- hand selection ------------------------------------------------------------------------


def hand(label, score):
    return Hand(points=np.zeros((21, 3), dtype=np.float32), handedness=label, score=score)


def test_select_hand_any_takes_most_confident():
    assert select_hand([hand("Left", 0.7), hand("Right", 0.9)]).handedness == "Right"


def test_select_hand_preference_ignores_other_hand():
    hands = [hand("Left", 0.7), hand("Right", 0.9)]
    assert select_hand(hands, "left").handedness == "Left"
    assert select_hand([hand("Right", 0.9)], "left") is None
    assert select_hand([], "any") is None


# --- fist ----------------------------------------------------------------------------------


def drive(ctrl, hand_, frames, start):
    out = []
    for i in range(frames):
        out.append(ctrl.update(hand_, round((start + i) * FRAME * 1000)))
    return out, start + frames


def test_holding_a_fist_does_nothing_and_input_still_works_afterwards():
    be = RecordingBackend(1000, 1000)
    cfg = Config()
    cfg.cursor.region = [0.0, 0.0, 1.0, 1.0]
    ctrl = CursorController(be, config=cfg)
    _, n = drive(ctrl, make_hand(**FIST), 120, 0)  # 4 s fist
    assert be.moves == [] and be.clicks == [] and be.button_events == []
    _, n = drive(ctrl, make_hand(**POINT), 10, n)
    assert be.moves  # the cursor works right away: nothing was locked


def test_old_config_with_safety_section_is_still_accepted(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text("[safety]\nlock_hold = 1.0\nstart_locked = false\n[scroll]\ninvert = true\n")
    assert cfgmod.load(p).scroll.invert


# --- calibration ---------------------------------------------------------------------------


def hold(session, point, start, seconds=1.8):
    p = 0.0
    t = start
    while t < start + seconds:
        p = session.update(point, t)
        t += FRAME
    return p, t


def test_calibration_captures_two_corners_after_holding_still():
    s = CalibrationSession(hold=1.5)
    _, t = hold(s, (0.25, 0.2), 0.0)
    assert s.step == 1 and s.points == [(0.25, 0.2)]
    _, t = hold(s, (0.75, 0.65), t)
    assert s.done
    r = s.region
    assert (r.left, r.top, r.right, r.bottom) == (0.25, 0.2, 0.75, 0.65)


def test_calibration_moving_resets_the_hold_timer():
    s = CalibrationSession(hold=1.5)
    for i in range(80):  # keeps moving: never captured
        s.update((0.2 + 0.01 * i, 0.3), i * FRAME)
    assert s.step == 0


def test_calibration_losing_the_finger_resets_progress():
    s = CalibrationSession(hold=1.5)
    hold(s, (0.3, 0.3), 0.0, seconds=1.0)
    assert s.update(None, 1.1) == 0.0
    assert s.step == 0


def test_calibration_rejects_degenerate_second_corner():
    s = CalibrationSession(hold=1.0)
    _, t = hold(s, (0.5, 0.5), 0.0, 1.2)
    _, t = hold(s, (0.52, 0.52), t, 1.2)  # barely moved from the first corner
    assert not s.done and s.message and len(s.points) == 1
    _, t = hold(s, (0.8, 0.8), t + 0.1, 1.5)
    assert s.done and s.message == ""


# --- doctor + overlay ----------------------------------------------------------------------


def test_doctor_exit_codes_and_output():
    lines = []
    ok = lambda: Check("a", True, "fine")  # noqa: E731
    warn = lambda: Check("b", False, "meh", fatal=False)  # noqa: E731
    bad = lambda: Check("c", False, "broken")  # noqa: E731
    assert run_doctor(checks=[ok, warn], out=lines.append) == 0
    assert run_doctor(checks=[ok, bad], out=lines.append) == 1
    assert any("[WARN] b" in line for line in lines) and any("[FAIL] c" in line for line in lines)


def test_overlay_calibration_draw():
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    draw_calibration(frame, "p", "m", 0.5, [(0.5, 0.5)])
    assert frame.any()
