# AirCursor

Control your mouse cursor with your hand in the air, using only a webcam.
See [PLAN.md](PLAN.md) for the design and roadmap.

**Status:** Phase 1: move the cursor with your index finger (Windows). Clicking and scrolling are not implemented yet.

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

### Phase 1 gestures

| Pose | Effect |
|---|---|
| Index finger out, other fingers curled (thumb either way) | Cursor follows your fingertip |
| Open palm, fist, anything else, or hand out of view | Cursor freezes |

The yellow rectangle in the preview is the active region: it maps to the whole screen, so you only need to move your hand within it.

## Development

```powershell
ruff check . ; ruff format --check . ; mypy aircursor ; pytest
```

On Linux, MediaPipe needs `libegl1 libgles2 libgl1`.
