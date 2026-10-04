import pytest

from aircursor.fps import FpsCounter


def test_fps_converges_to_steady_rate():
    t = [0.0]
    counter = FpsCounter(clock=lambda: t[0])
    for _ in range(200):
        t[0] += 1 / 30
        counter.tick()
    assert counter.fps == pytest.approx(30, rel=0.01)


def test_first_tick_reports_zero():
    assert FpsCounter(clock=lambda: 1.0).tick() == 0.0
