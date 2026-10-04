"""``aircursor doctor``: check that everything needed to run is in place."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass

from aircursor import config as config_mod


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    fatal: bool = True  # a failed non-fatal check is reported as a warning


def check_python() -> Check:
    v = sys.version_info
    return Check("Python >= 3.11", v >= (3, 11), f"{v.major}.{v.minor}.{v.micro}")


def check_platform() -> Check:
    ok = sys.platform == "win32"
    detail = sys.platform if ok else f"{sys.platform}: only Windows can move the cursor so far"
    return Check("Platform supported", ok, detail, fatal=False)


def check_config(path: str | None = None) -> Check:
    from pathlib import Path

    try:
        cfg_path = Path(path) if path else config_mod.default_path()
        config_mod.load(Path(path) if path else None)
    except config_mod.ConfigError as e:
        return Check("Config file", False, str(e))
    where = cfg_path if cfg_path.exists() else "not found, using defaults"
    return Check("Config file", True, str(where))


def check_model() -> Check:
    try:
        from aircursor.tracking.model import ensure_model

        return Check("Hand model", True, str(ensure_model()))
    except Exception as e:  # network, disk, permissions
        return Check("Hand model", False, f"could not obtain model: {e}")


def check_tracker() -> Check:
    try:
        from aircursor.tracking import HandTracker

        HandTracker().close()
        return Check("MediaPipe tracker", True, "loaded")
    except Exception as e:
        hint = (
            " (Linux: install libegl1 libgles2 libgl1)" if sys.platform.startswith("linux") else ""
        )
        return Check("MediaPipe tracker", False, f"{e}{hint}")


def check_camera(source: str = "0") -> Check:
    if not source.isdigit():
        return Check("Camera", True, f"using video file {source}")
    try:
        from aircursor.capture.source import CameraSource

        cam = CameraSource(int(source))
        try:
            item = cam.read()
        finally:
            cam.close()
        if item is None:
            return Check("Camera", False, f"camera {source} opened but gave no frames")
        h, w = item[0].shape[:2]
        return Check("Camera", True, f"camera {source}: {w}x{h}")
    except Exception as e:
        return Check("Camera", False, f"{e}. Is another app using it? Try --source 1.")


def check_backend() -> Check:
    try:
        from aircursor.actions.backend import make_backend

        w, h = make_backend().screen_size()
        return Check("Mouse control", True, f"screen {w}x{h}")
    except Exception as e:
        return Check("Mouse control", False, str(e), fatal=False)


def run_doctor(
    camera: str = "0",
    config_path: str | None = None,
    checks: list[Callable[[], Check]] | None = None,
    out: Callable[[str], None] = print,
) -> int:
    """Run all checks, print results, and return an exit code (0 = no fatal problems)."""
    checks = checks or [
        check_python,
        check_platform,
        lambda: check_config(config_path),
        check_model,
        check_tracker,
        lambda: check_camera(camera),
        check_backend,
    ]
    failed = False
    for make in checks:
        c = make()
        mark = "OK  " if c.ok else ("FAIL" if c.fatal else "WARN")
        out(f"[{mark}] {c.name}: {c.detail}")
        failed = failed or (not c.ok and c.fatal)
    out("All good." if not failed else "Problems found; fix the FAIL lines above.")
    return 1 if failed else 0
