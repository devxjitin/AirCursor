import numpy as np

from aircursor.tracking.landmarks import CONNECTIONS, Hand, Landmark


def make_hand() -> Hand:
    pts = np.zeros((21, 3), dtype=np.float32)
    pts[:, 0] = np.linspace(0.1, 0.9, 21)
    pts[:, 1] = 0.5
    return Hand(points=pts, handedness="Right", score=0.9)


def test_landmark_indices():
    assert Landmark.INDEX_TIP == 8 and Landmark.PINKY_TIP == 20
    assert all(0 <= a < 21 and 0 <= b < 21 for a, b in CONNECTIONS)


def test_pixel_points_scale():
    px = make_hand().pixel_points(200, 100)
    assert px.shape == (21, 2)
    assert tuple(px[0]) == (20, 50)


def test_mirrored_flips_x_only():
    hand = make_hand()
    m = hand.mirrored()
    np.testing.assert_allclose(m.points[:, 0], 1.0 - hand.points[:, 0])
    np.testing.assert_allclose(m.points[:, 1:], hand.points[:, 1:])
    assert hand.points[0, 0] == np.float32(0.1)  # original untouched
