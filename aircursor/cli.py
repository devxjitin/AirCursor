"""Command-line entry point."""

from __future__ import annotations

import argparse
import time
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import cv2

from aircursor import config as config_mod
from aircursor.actions.backend import InputBackend, RecordingBackend, make_backend
from aircursor.calibration import CalibrationSession
from aircursor.capture.source import Frame, open_source
from aircursor.config import Config, ConfigError
from aircursor.controller import ControllerState, CursorController
from aircursor.cursor.mapper import ActiveRegion
from aircursor.doctor import run_doctor
from aircursor.fps import FpsCounter
from aircursor.gestures.pose import Pose, classify
from aircursor.recording import read_frames, write_frame
from aircursor.tracking import HandTracker
from aircursor.tracking.landmarks import Landmark
from aircursor.ui.feedback import Feedback
from aircursor.ui.overlay import (
    draw_calibration,
    draw_hand,
    draw_lock,
    draw_region,
    draw_status,
)

WINDOW = "AirCursor (q / Esc to quit)"

_LABELS = {
    "single": "CLICK",
    "double": "DOUBLE CLICK",
    "drag_start": "DRAG",
    "drag_end": "DROP",
}
_SOUNDS = {"single": "click", "double": "double", "drag_start": "drag", "drag_end": "drop"}


def _event_label(state: ControllerState) -> str | None:
    """Short text describing the mouse action taken this frame, if any."""
    if state.lock_changed:
        return "LOCKED" if state.locked else "UNLOCKED"
    if state.click is not None:
        return _LABELS[state.click.value]
    if state.right_click:
        return "RIGHT CLICK"
    if state.scrolled:
        return "SCROLL"
    if state.zoomed:
        return "ZOOM"
    return None


def _sound_for(state: ControllerState) -> str | None:
    if state.lock_changed:
        return "lock" if state.locked else "unlock"
    if state.click is not None:
        return _SOUNDS[state.click.value]
    return "right" if state.right_click else None


def run(
    source: str,
    controller: CursorController | None = None,
    show: bool = True,
    max_frames: int | None = None,
    cfg: Config | None = None,
    record_to: Path | None = None,
) -> int:
    """Track hands from ``source``; optionally drive the cursor. Returns frames processed."""
    cfg = cfg or Config()
    fps = FpsCounter()
    feedback = Feedback(cfg.feedback.sound)
    frames = 0
    flash_until = 0.0
    flash_text = ""
    src = open_source(source, cfg.camera.width, cfg.camera.height)
    rec = open(record_to, "w", encoding="utf-8") if record_to else None
    try:
        with HandTracker(preferred=cfg.hand.preferred) as tracker:
            while max_frames is None or frames < max_frames:
                item = src.read()
                if item is None:
                    break
                frame, ts = item
                hand = tracker.process(frame, ts)
                if rec is not None:
                    write_frame(rec, ts, hand)
                state = controller.update(hand, ts) if controller else None
                frames += 1
                if state and (label := _event_label(state)):
                    flash_text, flash_until = label, ts + 400
                    if not show and label not in ("SCROLL", "ZOOM"):
                        print(f"{label} at {state.click_pos or state.cursor}")
                if state and (sound := _sound_for(state)):
                    feedback.notify(sound)
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
                    draw_status(
                        frame,
                        current,
                        shown,
                        state.pose.value if state else None,
                        flash_text if ts < flash_until else None,
                    )
                    if state:
                        draw_lock(frame, state.locked, state.lock_progress, cfg.safety.lock_hold)
                    cv2.imshow(WINDOW, frame)
                    if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                        break
                elif frames % 30 == 0:
                    pose = f", pose={state.pose.value}" if state else ""
                    lock = ", LOCKED" if state and state.locked else ""
                    print(f"{current:.1f} FPS, hand={'yes' if hand else 'no'}{pose}{lock}")
    finally:
        if controller is not None:
            controller.release_all()  # never leave a mouse button stuck down
        src.close()
        if rec is not None:
            rec.close()
        if show:
            cv2.destroyAllWindows()
    return frames


def replay(path: Path | str, controller: CursorController) -> list[tuple[int, str]]:
    """Feed a recording through ``controller``; return ``(timestamp_ms, action)`` per event."""
    events: list[tuple[int, str]] = []
    try:
        for ts, hand in read_frames(path):
            state = controller.update(hand, ts)
            if label := _event_label(state):
                events.append((ts, label))
    finally:
        controller.release_all()
    return events


def run_calibration(source: str, cfg: Config, cfg_path: Path | None) -> ActiveRegion | None:
    """Interactive calibration window. Saves the region to the config file when finished."""
    session = CalibrationSession()
    src = open_source(source, cfg.camera.width, cfg.camera.height)
    done_at: float | None = None
    try:
        with HandTracker(preferred=cfg.hand.preferred) as tracker:
            while True:
                item = src.read()
                if item is None:
                    return None
                frame, ts = item
                hand = tracker.process(frame, ts)
                frame = cast(Frame, cv2.flip(frame, 1))
                tip = None
                if hand is not None and classify(hand) is Pose.POINT:
                    m = hand.mirrored()
                    tip = (
                        float(m.points[Landmark.INDEX_TIP, 0]),
                        float(m.points[Landmark.INDEX_TIP, 1]),
                    )
                progress = session.update(tip, ts / 1000.0)
                if hand is not None:
                    draw_hand(frame, hand.mirrored())
                draw_calibration(frame, session.prompt, session.message, progress, session.points)
                if session.done:
                    draw_region(frame, session.region)
                    done_at = done_at or time.monotonic()
                cv2.imshow("AirCursor calibration (q / Esc to cancel)", frame)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    return None
                if done_at is not None and time.monotonic() - done_at > 1.5:
                    break
    finally:
        src.close()
        cv2.destroyAllWindows()
    region = session.region
    cfg.cursor.region = [region.left, region.top, region.right, region.bottom]
    config_mod.validate(cfg)
    print(f"Saved to {config_mod.save(cfg, cfg_path)}")
    return region


def _load_config(path: str | None) -> Config:
    return config_mod.load(Path(path) if path else None)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aircursor")
    parser.add_argument(
        "--config", help="config file (default: per-user location, see `config path`)"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_ in (
        ("debug", "show live hand landmarks and FPS (does not move the cursor)"),
        ("run", "control the mouse with hand gestures"),
        ("calibrate", "learn the area of the camera image you can comfortably reach"),
    ):
        p = sub.add_parser(name, help=help_)
        p.add_argument(
            "--source", default=None, help="camera index or video file (default: config)"
        )
        if name != "calibrate":
            p.add_argument("--no-window", action="store_true", help="headless; print status")
            p.add_argument("--max-frames", type=int, default=None, help="stop after N frames")
        if name == "run":
            p.add_argument("--dry-run", action="store_true", help="log only; don't move the cursor")
            p.add_argument("--invert-scroll", action="store_true", help="touch-style scrolling")
            p.add_argument("--start-locked", action="store_true", help="start with input locked")
    rec = sub.add_parser("record", help="record hand landmarks (no video) to a file")
    rec.add_argument("output", help="file to write (.jsonl)")
    rec.add_argument("--source", default=None, help="camera index or video file")
    rec.add_argument("--no-window", action="store_true", help="headless")
    rec.add_argument("--max-frames", type=int, default=None, help="stop after N frames")
    rep = sub.add_parser("replay", help="run a recording through the gestures (no mouse)")
    rep.add_argument("input", help="recording made with `record`")
    doc = sub.add_parser("doctor", help="check camera, model, permissions and config")
    doc.add_argument("--source", default=None, help="camera index to test (default: config)")
    conf = sub.add_parser("config", help="show, locate or create the config file")
    conf.add_argument("action", choices=["path", "show", "init"])
    args = parser.parse_args(argv)

    try:
        if args.command == "config":
            path = Path(args.config) if args.config else config_mod.default_path()
            if args.action == "path":
                print(path)
            elif args.action == "show":
                print(config_mod.to_toml(config_mod.load(path if args.config else None)))
            elif path.exists():
                print(f"{path} already exists; not overwriting.")
                return 1
            else:
                print(f"Wrote {config_mod.save(Config(), path)}")
            return 0

        cfg = _load_config(args.config)
        if args.command == "replay":
            events = replay(args.input, CursorController(RecordingBackend(), config=cfg))
            for ts, label in events:
                print(f"{ts / 1000:8.3f}s  {label}")
            print(f"{len(events)} events")
            return 0
        source = args.source or cfg.camera.source
        if args.command == "doctor":
            return run_doctor(source, args.config)
        if args.command == "calibrate":
            region = run_calibration(source, cfg, Path(args.config) if args.config else None)
            if region is None:
                print("Calibration cancelled; nothing saved.")
                return 1
            return 0

        if args.command == "record":
            n = run(
                source,
                None,
                show=not args.no_window,
                max_frames=args.max_frames,
                cfg=cfg,
                record_to=Path(args.output),
            )
            print(f"Recorded {n} frames to {args.output}")
            return 0

        controller = None
        if args.command == "run":
            cfg.scroll.invert = cfg.scroll.invert or args.invert_scroll
            cfg.safety.start_locked = cfg.safety.start_locked or args.start_locked
            backend: InputBackend = RecordingBackend() if args.dry_run else make_backend()
            controller = CursorController(backend, config=cfg)
        run(source, controller, show=not args.no_window, max_frames=args.max_frames, cfg=cfg)
    except ConfigError as e:
        print(f"Config error: {e}")
        return 2
    return 0
