"""Choosing which detected hand controls the cursor."""

from __future__ import annotations

from collections.abc import Sequence

from aircursor.tracking.landmarks import Hand


def select_hand(hands: Sequence[Hand], preferred: str = "any") -> Hand | None:
    """Pick the controlling hand. ``preferred`` is "any", "left" or "right" (the user's hand).

    With a preference, the other hand is ignored entirely, so waving it around can't take over.
    """
    if preferred != "any":
        hands = [h for h in hands if h.handedness.lower() == preferred]
    return max(hands, key=lambda h: h.score, default=None)
