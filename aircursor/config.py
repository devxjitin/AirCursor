"""User configuration (TOML), with validation and a writer for generated files."""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """The config file is unreadable or contains invalid values."""


@dataclass
class CameraConfig:
    source: str = "0"  # camera index, or a video file path
    width: int = 640
    height: int = 480


@dataclass
class HandConfig:
    preferred: str = "any"  # "any", "left" or "right": which of your hands controls the cursor


@dataclass
class CursorConfig:
    # Part of the mirrored camera image that spans the whole screen: left, top, right, bottom.
    region: list[float] = field(default_factory=lambda: [0.2, 0.15, 0.8, 0.7])
    min_cutoff: float = 1.5  # lower = smoother but laggier when moving slowly
    beta: float = 8.0  # higher = less lag when moving fast


@dataclass
class ClickConfig:
    pinch_close: float = 0.30  # thumb-finger distance (fraction of hand size) that starts a pinch
    pinch_open: float = 0.50  # distance that ends it
    max_hold: float = 0.5  # seconds: longer than this and a pinch becomes a drag
    double_window: float = 0.45  # seconds between two taps for a double click
    lookback: float = 0.20  # seconds: click lands where the cursor was this long before the pinch


@dataclass
class ScrollConfig:
    gain: float = 800.0  # wheel units per hand-size of travel (120 units = one notch)
    accel: float = 0.5  # extra distance for faster movement
    invert: bool = False  # True: moving the hand up scrolls the page down (touch style)


@dataclass
class SafetyConfig:
    lock_hold: float = 1.0  # seconds a fist must be held to lock / unlock all input
    start_locked: bool = False


@dataclass
class FeedbackConfig:
    sound: bool = True  # short beeps on click / drag / lock (Windows only)


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    hand: HandConfig = field(default_factory=HandConfig)
    cursor: CursorConfig = field(default_factory=CursorConfig)
    click: ClickConfig = field(default_factory=ClickConfig)
    scroll: ScrollConfig = field(default_factory=ScrollConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    feedback: FeedbackConfig = field(default_factory=FeedbackConfig)


def default_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "aircursor" / "config.toml"


def _build(cls: type, data: dict[str, Any], where: str) -> Any:
    known = {f.name: f for f in fields(cls)}
    for key in data:
        if key not in known:
            raise ConfigError(f"unknown setting {where}{key!r} (valid: {', '.join(known)})")
    obj = cls()
    for key, value in data.items():
        current = getattr(obj, key)
        if is_dataclass(current):
            if not isinstance(value, dict):
                raise ConfigError(f"[{where}{key}] must be a table")
            value = _build(type(current), value, f"{where}{key}.")
        elif isinstance(current, bool):
            if not isinstance(value, bool):
                raise ConfigError(f"{where}{key} must be true or false")
        elif isinstance(current, (int, float)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ConfigError(f"{where}{key} must be a number")
            value = type(current)(value)
        elif isinstance(current, str):
            if not isinstance(value, str):
                raise ConfigError(f"{where}{key} must be text")
        elif isinstance(current, list) and not (
            isinstance(value, list) and all(isinstance(v, (int, float)) for v in value)
        ):
            raise ConfigError(f"{where}{key} must be a list of numbers")
        setattr(obj, key, value)
    return obj


def validate(cfg: Config) -> Config:
    left, top, right, bottom = cfg.cursor.region if len(cfg.cursor.region) == 4 else (0, 0, 0, 0)
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise ConfigError("cursor.region must be [left, top, right, bottom] within 0..1")
    if right - left < 0.1 or bottom - top < 0.1:
        raise ConfigError("cursor.region is too small (at least 0.1 of the image in each axis)")
    if cfg.hand.preferred not in ("any", "left", "right"):
        raise ConfigError('hand.preferred must be "any", "left" or "right"')
    c = cfg.click
    if not 0 < c.pinch_close < c.pinch_open:
        raise ConfigError("click.pinch_close must be above 0 and below click.pinch_open")
    if c.max_hold <= 0 or c.double_window < 0 or c.lookback < 0:
        raise ConfigError("click timings must be positive")
    if cfg.safety.lock_hold <= 0:
        raise ConfigError("safety.lock_hold must be positive")
    if cfg.camera.width <= 0 or cfg.camera.height <= 0:
        raise ConfigError("camera width and height must be positive")
    return cfg


def from_dict(data: dict[str, Any]) -> Config:
    return validate(_build(Config, data, ""))


def load(path: Path | None = None) -> Config:
    """Load ``path`` (default location if None). A missing default file gives the defaults."""
    explicit = path is not None
    path = path or default_path()
    if not path.exists():
        if explicit:
            raise ConfigError(f"config file not found: {path}")
        return Config()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from e
    try:
        return from_dict(data)
    except ConfigError as e:
        raise ConfigError(f"{path}: {e}") from e


def _fmt(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, list):
        return "[" + ", ".join(_fmt(v) for v in value) + "]"
    return repr(value)


def to_toml(cfg: Config) -> str:
    lines: list[str] = []
    for section, values in asdict(cfg).items():
        lines.append(f"[{section}]")
        lines += [f"{k} = {_fmt(v)}" for k, v in values.items()]
        lines.append("")
    return "\n".join(lines)


def save(cfg: Config, path: Path | None = None) -> Path:
    path = path or default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_toml(cfg), encoding="utf-8")
    return path
