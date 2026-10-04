import cv2
import numpy as np
import pytest

from aircursor.capture.source import VideoFileSource, open_source
from aircursor.tracking.landmarks import Hand
from aircursor.ui.overlay import draw_hand, draw_status


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "clip.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
    for _ in range(5):
        writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    writer.release()
    return path


def test_video_source_reads_all_frames_with_timestamps(video):
    src = VideoFileSource(video)
    stamps = []
    while (item := src.read()) is not None:
        frame, ts = item
        assert frame.shape == (48, 64, 3)
        stamps.append(ts)
    src.close()
    assert stamps == [0, 100, 200, 300, 400]


def test_open_source_missing_file_raises(tmp_path):
    with pytest.raises(RuntimeError):
        open_source(str(tmp_path / "nope.mp4"))


def test_overlay_draws_pixels():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    pts = np.random.default_rng(0).random((21, 3)).astype(np.float32)
    hand = Hand(points=pts, handedness="Left", score=0.8)
    draw_hand(frame, hand)
    draw_status(frame, 30.0, hand)
    assert frame.any()
