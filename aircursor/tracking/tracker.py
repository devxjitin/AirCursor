"""MediaPipe HandLandmarker wrapper that yields :class:`Hand` objects."""

from __future__ import annotations

from pathlib import Path
from types import TracebackType

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision
from numpy.typing import NDArray

from aircursor.tracking.landmarks import Hand
from aircursor.tracking.model import DEFAULT_MODEL_PATH, ensure_model


class HandTracker:
    """Detects the most confident hand in each frame.

    Frames must be fed with non-decreasing timestamps (milliseconds).
    """

    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_PATH,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(ensure_model(model_path))),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._last_ts = -1

    def process(self, frame_bgr: NDArray[np.uint8], timestamp_ms: int) -> Hand | None:
        """Run detection on one BGR frame; return the hand or ``None``."""
        # MediaPipe requires strictly increasing timestamps.
        timestamp_ms = max(timestamp_ms, self._last_ts + 1)
        self._last_ts = timestamp_ms
        rgb = np.ascontiguousarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(image, timestamp_ms)
        if not result.hand_landmarks:
            return None
        lms = result.hand_landmarks[0]
        points = np.array([[lm.x, lm.y, lm.z] for lm in lms], dtype=np.float32)
        category = result.handedness[0][0]
        return Hand(points=points, handedness=category.category_name, score=category.score)

    def close(self) -> None:
        self._landmarker.close()

    def __enter__(self) -> HandTracker:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
