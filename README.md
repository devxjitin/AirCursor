# AirCursor

Control your mouse cursor with your hand in the air, using only a webcam.
See [PLAN.md](PLAN.md) for the design and roadmap.

**Status:** Phase 5 (partial): move, click, double-click, right-click, scroll (with flick inertia), zoom and drag (Windows), plus lock gesture, calibration, config file, `doctor`, and landmark record/replay.

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

Quick guide (the emoji show your hand shape; arrows show how to move it):

| Gesture | Action | How |
|:---:|---|---|
| ☝️ | **Move cursor** | Index finger out, other fingers curled (thumb in or out). The cursor follows your fingertip |
| 🤏 | **Left click** | Pinch thumb and index finger together, then let go quickly. Fires on release |
| 🤏 🤏 | **Double click** | Two quick pinches, within about 0.45 s |
| 🤏 ⏳ → ↔️ | **Drag and drop** | Pinch and hold for more than 0.5 s: the button goes down and the cursor follows your hand. Let go of the pinch to drop |
| ✌️ + 🤏 | **Right click** | Keep index and middle fingers out, touch your thumb to your **middle** fingertip, then let go quickly |
| ✌️ ↕️ ↔️ | **Scroll** | Index and middle fingers out together (ring and little finger curled), then move your hand up, down, left or right. A quick flick keeps gliding; pinching stops it |
| 👆👆👆 ↕️ | **Zoom** | Index, middle and ring fingers out (little finger curled), then move your hand up to zoom in or down to zoom out (Ctrl + mouse wheel) |
| ✊ ⏳ | **Lock / unlock** | Hold a fist for 1 s. All input is blocked until you hold a fist for 1 s again. A progress bar fills while you hold. Locking mid-drag releases the button |
| ✋ or 🚫 | **Pause** | Open palm, any other hand shape, or no hand in view: the cursor freezes |

Legend: ⏳ = hold it for a moment, ↕️ ↔️ = move your hand, 🚫 = hand out of view.

Pinching moves your fingertip, so the click lands where the cursor was just *before* you started to pinch, and the cursor is held still until just after you release. Keep your middle, ring and little fingers curled while pinching with the index finger. For a right click, keep the index finger out and touch your thumb to your middle fingertip. Faster hand movement scrolls disproportionately further; `aircursor run --invert-scroll` flips the direction. If the hand is lost mid-drag the button is released after 0.3 s.

The yellow rectangle in the preview is the active region: it maps to the whole screen, so you only need to move your hand within it.

## Development

```powershell
ruff check . ; ruff format --check . ; mypy aircursor ; pytest
```

On Linux, MediaPipe needs `libegl1 libgles2 libgl1`.

## Recording and replaying

`aircursor record session.jsonl` saves hand landmarks (numbers only, no video) while you use the camera.
`aircursor replay session.jsonl` runs them through the gesture logic offline, never touching your mouse, and
prints each action with its timestamp. Use it to tune thresholds, or attach a recording to a bug report.

## Configuration

`aircursor config init` writes a default file to the location shown by `aircursor config path`
(`%APPDATA%\aircursor\config.toml` on Windows). Any setting you leave out keeps its default;
unknown or invalid settings are reported by name. Use `--config FILE` on any command to use another file.

| Section | What it controls |
|---|---|
| `[camera]` | `source` (index or video file), `width`, `height` |
| `[hand]` | `preferred = "any" \| "left" \| "right"`: which hand controls the cursor. With a preference, the other hand is ignored (left-handed mode: `"left"`) |
| `[cursor]` | `region` (set by `calibrate`), `min_cutoff` / `beta` smoothing |
| `[click]` | pinch thresholds, `max_hold`, `double_window`, `lookback` |
| `[scroll]` | `gain`, `accel`, `invert`, `inertia`, `inertia_time` |
| `[zoom]` | `enabled`, `gain`, `invert` |
| `[safety]` | `lock_hold` seconds, `start_locked` |
| `[feedback]` | `sound`: short beeps for click / drag / lock (Windows) |

The preview shows `LOCKED` banners and a flash for each action. `aircursor run --start-locked` starts locked.
