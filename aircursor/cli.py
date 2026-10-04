"""Command-line entry point."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import cast

import cv2

from aircursor.actions.backend import InputBackend, RecordingBackend, make_backend
from aircursor.capture.source import Frame, open_source
from aircursor.controller import CursorController
from aircursor.fps import FpsCounter
from aircursor.tracking import HandTracker
from aircursor.ui.overlay import draw_hand, draw_region, draw_status

WINDOW = "AirCursor (q / Esc to quit)"


def run(
    source: str,
    controller: CursorController | None = None,
    show: bool = True,
    max_frames: int | None = None,
) -> int:
    """Track hands from ``source``; optionally drive the cursor. Returns frames processed."""
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
                state = controller.update(hand, ts) if controller else None
                frames += 1
                current = fps.tick()
                if show:
                    mirror = source.isdigit()  # webcams are shown like a mirror
                    if mirror:
                        frame = cast(Frame, cv2.flip(frame, 1))
                    shown = hand.mirrored() if (hand and mirror) else hand
                    if shown is not None:
                        draw_hand(frame, shown)
                    if controller is not None:
                        draw_region(frame, controller.mapper.region)
                    draw_status(frame, current, shown, state.pose.value if state else None)
                    cv2.imshow(WINDOW, frame)
                    if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                        break
                elif frames % 30 == 0:
                    pose = f", pose={state.pose.value}" if state else ""
                    print(f"{current:.1f} FPS, hand={'yes' if hand else 'no'}{pose}")
    finally:
        src.close()
        if show:
            cv2.destroyAllWindows()
    return frames


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aircursor")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_ in (
        ("debug", "show live hand landmarks and FPS (does not move the cursor)"),
        ("run", "control the mouse cursor with your index finger"),
    ):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--source", default="0", help="camera index or video file (default: 0)")
        p.add_argument("--no-window", action="store_true", help="headless; print status to stdout")
        p.add_argument("--max-frames", type=int, default=None, help="stop after N frames")
        if name == "run":
            p.add_argument(
                "--dry-run", action="store_true", help="do not move the real cursor (log only)"
            )
    args = parser.parse_args(argv)

    controller = None
    if args.command == "run":
        backend: InputBackend = RecordingBackend() if args.dry_run else make_backend()
        controller = CursorController(backend)
    run(args.source, controller, show=not args.no_window, max_frames=args.max_frames)
    return 0
