import numpy as np
import pytest

from aircursor.tracking.model import DEFAULT_MODEL_PATH, ensure_model

pytestmark = pytest.mark.skipif(
    not DEFAULT_MODEL_PATH.exists(), reason="hand_landmarker.task not downloaded"
)


def test_ensure_model_returns_existing_path():
    assert ensure_model() == DEFAULT_MODEL_PATH


def test_blank_frames_have_no_hand_and_tolerate_repeat_timestamps():
    from aircursor.tracking import HandTracker

    blank = np.zeros((240, 320, 3), dtype=np.uint8)
    with HandTracker() as tracker:
        assert tracker.process(blank, 0) is None
        assert tracker.process(blank, 0) is None  # duplicate ts must not crash
        assert tracker.process(blank, 33) is None
