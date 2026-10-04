# AirCursor

Control your mouse cursor with your hand in the air, using only a webcam.
See [PLAN.md](PLAN.md) for the design and roadmap.

**Status:** Phase 0 (foundations): live hand-landmark debug view. Cursor control is not implemented yet.

## Setup (Windows)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

The MediaPipe hand model (~8 MB) is downloaded to `models/` on first run.

## Try it

```powershell
aircursor debug                      # webcam 0, mirrored preview with landmarks + FPS
aircursor debug --source 1           # another camera
aircursor debug --source clip.mp4    # a video file
aircursor debug --no-window --max-frames 300   # headless, prints FPS
```

Press `q` or `Esc` to quit.

## Development

```powershell
ruff check . ; ruff format --check . ; mypy aircursor ; pytest
```

On Linux, MediaPipe needs `libegl1 libgles2 libgl1`.
