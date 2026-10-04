# AirCursor

Control your mouse cursor with your hand in the air, using only a webcam.
See [PLAN.md](PLAN.md) for the design and roadmap.

**Status:** Phase 4: move, click, double-click, right-click, scroll and drag (Windows), with a lock gesture, calibration, config file and `doctor`.

## Setup (Windows)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

The MediaPipe hand model (~8 MB) is downloaded to `models/` on first run.

## First run

```powershell
aircursor doctor      # checks Python, camera, model, mouse access, config
aircursor calibrate   # point at the top-left, then bottom-right, of your comfortable area
aircursor run --dry-run   # try it without moving the real cursor
aircursor run
```

## Commands

```powershell
aircursor run                        # control the cursor: point with your index finger only
aircursor run --dry-run              # same, but only logs; does not move the real cursor
aircursor debug                      # webcam 0, mirrored preview with landmarks + FPS
aircursor debug --source 1           # another camera
aircursor debug --source clip.mp4    # a video file
aircursor debug --no-window --max-frames 300   # headless, prints FPS
```

Press `q` or `Esc` in the preview window to quit.

### Gestures

| Pose | Effect |
|---|---|
| Index finger out, other fingers curled (thumb either way) | Cursor follows your fingertip |
| Pinch thumb and index together, then release quickly | Left click (fires on release) |
| Two quick pinches (within ~0.45 s) | Double click |
| Pinch held longer than 0.5 s | Drag: button goes down, cursor follows your hand, release the pinch to drop |
| Pinch thumb and **middle** finger, release quickly | Right click |
| Index + middle fingers out together (ring and little finger curled), move hand up/down/left/right | Scroll |
| **Hold a fist for 1 s** | Lock: all input is blocked until you hold a fist for 1 s again (a progress bar fills while you hold). Locking mid-drag releases the button |
| Open palm, anything else, or hand out of view | Cursor freezes |

Pinching moves your fingertip, so the click lands where the cursor was just *before* you started to pinch, and the cursor is held still until just after you release. Keep your middle, ring and little fingers curled while pinching with the index finger. For a right click, keep the index finger out and touch your thumb to your middle fingertip. Faster hand movement scrolls disproportionately further; `aircursor run --invert-scroll` flips the direction. If the hand is lost mid-drag the button is released after 0.3 s.

The yellow rectangle in the preview is the active region: it maps to the whole screen, so you only need to move your hand within it.

## Development

```powershell
ruff check . ; ruff format --check . ; mypy aircursor ; pytest
```

On Linux, MediaPipe needs `libegl1 libgles2 libgl1`.

## Configuration

`aircursor config init` writes a commented-free default file to `aircursor config path`
(`%APPDATA%\aircursor\config.toml` on Windows). Any setting you leave out keeps its default;
unknown or invalid settings are reported by name. Use `--config FILE` on any command to use another file.

| Section | What it controls |
|---|---|
| `[camera]` | `source` (index or video file), `width`, `height` |
| `[hand]` | `preferred = "any" \| "left" \| "right"`: which hand controls the cursor. With a preference, the other hand is ignored (left-handed mode: `"left"`) |
| `[cursor]` | `region` (set by `calibrate`), `min_cutoff` / `beta` smoothing |
| `[click]` | pinch thresholds, `max_hold`, `double_window`, `lookback` |
| `[scroll]` | `gain`, `accel`, `invert` |
| `[safety]` | `lock_hold` seconds, `start_locked` |
| `[feedback]` | `sound`: short beeps for click / drag / lock (Windows) |

The preview shows `LOCKED` banners and a flash for each action. `aircursor run --start-locked` starts locked.
