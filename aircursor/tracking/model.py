"""Locate (and download on first use) the MediaPipe hand landmarker model."""

from __future__ import annotations

import urllib.request
from pathlib import Path

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)
DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "hand_landmarker.task"


def ensure_model(path: Path = DEFAULT_MODEL_PATH, url: str = MODEL_URL) -> Path:
    """Return ``path``, downloading the model there first if it does not exist."""
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    try:
        urllib.request.urlretrieve(url, tmp)  # noqa: S310 - fixed https URL
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
    return path
