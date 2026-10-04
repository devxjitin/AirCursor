"""Record hand-landmark sessions to JSON Lines and replay them through the controller.

Recordings hold only landmark coordinates (no camera images), so they are small and private.
They let you tune gestures offline, share a problem case, or build regression tests.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import IO

import numpy as np

from aircursor.tracking.landmarks import Hand


def frame_to_json(timestamp_ms: int, hand: Hand | None) -> str:
    rec: dict[str, object] = {"t": timestamp_ms, "hand": None}
    if hand is not None:
        rec["hand"] = {
            "points": np.round(hand.points, 5).tolist(),
            "handedness": hand.handedness,
            "score": round(float(hand.score), 4),
        }
    return json.dumps(rec, separators=(",", ":"))


def write_frame(fp: IO[str], timestamp_ms: int, hand: Hand | None) -> None:
    fp.write(frame_to_json(timestamp_ms, hand) + "\n")


def read_frames(path: Path | str) -> Iterator[tuple[int, Hand | None]]:
    """Yield ``(timestamp_ms, hand_or_None)`` from a recording."""
    with open(path, encoding="utf-8") as fp:
        for n, line in enumerate(fp, 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                h = rec["hand"]
                hand = (
                    None
                    if h is None
                    else Hand(
                        points=np.array(h["points"], dtype=np.float32).reshape(21, 3),
                        handedness=h["handedness"],
                        score=float(h["score"]),
                    )
                )
                yield int(rec["t"]), hand
            except (KeyError, ValueError, TypeError) as e:
                raise ValueError(f"{path}:{n}: bad recording line ({e})") from e
