"""Short audio cues so you know an action registered without looking at the screen."""

from __future__ import annotations

import sys
import threading

# event -> list of (frequency Hz, duration ms)
_TONES: dict[str, list[tuple[int, int]]] = {
    "click": [(1000, 30)],
    "double": [(1000, 25), (1300, 25)],
    "right": [(700, 40)],
    "drag": [(600, 40), (900, 40)],
    "drop": [(900, 40), (600, 40)],
}


class Feedback:
    """Plays a beep per event on Windows (on a background thread so frames never stall)."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled and sys.platform == "win32"
        self._lock = threading.Lock()

    def notify(self, event: str) -> None:
        tones = _TONES.get(event)
        if not self.enabled or tones is None:
            return
        threading.Thread(target=self._play, args=(tones,), daemon=True).start()

    def _play(self, tones: list[tuple[int, int]]) -> None:
        import winsound  # Windows only

        with self._lock:  # serialise so overlapping cues don't pile up
            for freq, ms in tones:
                winsound.Beep(freq, ms)  # type: ignore[attr-defined,unused-ignore]
