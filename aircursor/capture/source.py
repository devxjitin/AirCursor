"""Frame sources: a live webcam (threaded, latest-frame-only) and video files."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Protocol, cast

import cv2
import numpy as np
from numpy.typing import NDArray

Frame = NDArray[np.uint8]


class FrameSource(Protocol):
    def read(self) -> tuple[Frame, int] | None:
        """Return ``(bgr_frame, timestamp_ms)`` or ``None`` when the source is exhausted."""

    def close(self) -> None: ...


class CameraSource:
    """Webcam capture on a background thread so ``read`` never returns a stale queued frame."""

    def __init__(self, index: int = 0, width: int = 640, height: int = 480) -> None:
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        self._cap = cv2.VideoCapture(index, backend)
        if not self._cap.isOpened():
            raise RuntimeError(f"Could not open camera {index}")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._lock = threading.Lock()
        self._latest: tuple[Frame, int] | None = None
        self._seq = 0
        self._seen = 0
        self._new_frame = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._start = time.monotonic()
        self._thread = threading.Thread(target=self._run, name="camera", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            ok, frame = self._cap.read()
            if not ok:
                time.sleep(0.005)
                continue
            ts = int((time.monotonic() - self._start) * 1000)
            with self._new_frame:
                self._latest = (cast(Frame, frame), ts)
                self._seq += 1
                self._new_frame.notify_all()

    def read(self) -> tuple[Frame, int] | None:
        """Block until a frame newer than the last returned one is available."""
        with self._new_frame:
            while self._seq == self._seen:
                if self._stop.is_set():
                    return None
                self._new_frame.wait(timeout=0.5)
            self._seen = self._seq
            return self._latest

    def close(self) -> None:
        self._stop.set()
        with self._new_frame:
            self._new_frame.notify_all()
        self._thread.join(timeout=2)
        self._cap.release()


class VideoFileSource:
    """Reads frames from a video file, timestamped by the file's own frame clock."""

    def __init__(self, path: Path | str) -> None:
        self._cap = cv2.VideoCapture(str(path))
        if not self._cap.isOpened():
            raise RuntimeError(f"Could not open video file {path}")
        self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self._n = 0

    def read(self) -> tuple[Frame, int] | None:
        ok, frame = self._cap.read()
        if not ok:
            return None
        ts = int(self._n * 1000 / self._fps)
        self._n += 1
        return cast(Frame, frame), ts

    def close(self) -> None:
        self._cap.release()


def open_source(spec: str, width: int = 640, height: int = 480) -> FrameSource:
    """Open ``spec``: an integer is a camera index, anything else is a video file path."""
    if spec.isdigit():
        return CameraSource(int(spec), width, height)
    return VideoFileSource(spec)
