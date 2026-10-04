"""Command-line entry point."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import cast

import cv2

from aircursor.capture.source import Frame, open_source
from aircursor.fps import FpsCounter
from aircursor.tracking import HandTracker
from aircursor.ui.overlay import draw_hand, draw_status

WINDOW = "AirCursor debug (q / Esc to quit)"


def run_debug(source: str, show: bool = True, max_frames: int | None = None) -> int:
    """Track hands from ``source`` and show landmarks and FPS. Returns frames processed."""
    fps = FpsCounter()
    frames = 0
    src = open_source(source)
    try:
        with HandTracker() as tracker:
            while max_frames is None or frames < max_frames:
                item = src.read()
                if item is None:
                    break
                frame, ts = item
                hand = tracker.process(frame, ts)
                frames += 1
                current = fps.tick()
                if show:
                    if source.isdigit():
                        frame = cast(Frame, cv2.flip(frame, 1))  # mirror webcam like a mirror
                        hand = hand.mirrored() if hand else None
                    if hand is not None:
                        draw_hand(frame, hand)
                    draw_status(frame, current, hand)
                    cv2.imshow(WINDOW, frame)
                    if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                        break
                elif frames % 30 == 0:
                    print(f"{current:.1f} FPS, hand={'yes' if hand else 'no'}")
    finally:
        src.close()
        if show:
            cv2.destroyAllWindows()
    return frames


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aircursor")
    sub = parser.add_subparsers(dest="command", required=True)
    dbg = sub.add_parser("debug", help="show live hand landmarks and FPS")
    dbg.add_argument("--source", default="0", help="camera index or video file (default: 0)")
    dbg.add_argument("--no-window", action="store_true", help="headless; print FPS to stdout")
    dbg.add_argument("--max-frames", type=int, default=None, help="stop after N frames")
    args = parser.parse_args(argv)
    if args.command == "debug":
        run_debug(args.source, show=not args.no_window, max_frames=args.max_frames)
    return 0
