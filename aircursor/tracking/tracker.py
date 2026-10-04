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
from aircursor.tracking.select import select_hand


class HandTracker:
    """Detects the controlling hand in each frame.

    Frames must be fed with non-decreasing timestamps (milliseconds). ``preferred`` is "any",
    "left" or "right" (the user's own hand); with a preference the other hand is ignored.
    """

    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_PATH,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        preferred: str = "any",
    ) -> None:
        self._preferred = preferred
        options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(ensure_model(model_path))),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1 if preferred == "any" else 2,
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
        hands = []
        for lms, cats in zip(result.hand_landmarks, result.handedness, strict=False):
            points = np.array([[lm.x, lm.y, lm.z] for lm in lms], dtype=np.float32)
            # MediaPipe assumes a mirrored (selfie) image. We feed it the raw frame, so its
            # "Left"/"Right" are the wrong way round for the person in front of the camera.
            label = "Right" if cats[0].category_name == "Left" else "Left"
            hands.append(Hand(points=points, handedness=label, score=cats[0].score))
        return select_hand(hands, self._preferred)

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
