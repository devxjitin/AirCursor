# AirCursor

Control your mouse cursor with your hand in the air, using only a webcam.
See [PLAN.md](PLAN.md) for the design and roadmap.

**Status:** Phase 2: move with your index finger, click and double-click by pinching (Windows). Scroll, right-click and drag are not implemented yet.

## Setup (Windows)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

The MediaPipe hand model (~8 MB) is downloaded to `models/` on first run.

## Try it

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
| Pinch held longer than 0.5 s | No click (reserved for drag) |
| Open palm, fist, anything else, or hand out of view | Cursor freezes |

Pinching moves your fingertip, so the click lands where the cursor was just *before* you started to pinch, and the cursor is held still until just after you release. Keep your middle, ring and little fingers curled while pinching.

The yellow rectangle in the preview is the active region: it maps to the whole screen, so you only need to move your hand within it.

## Development

```powershell
ruff check . ; ruff format --check . ; mypy aircursor ; pytest
```

On Linux, MediaPipe needs `libegl1 libgles2 libgl1`.
