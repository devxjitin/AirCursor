# AirCursor — Project Plan

Control the mouse cursor with your hand in the air, using only a webcam.
Move a finger to move the cursor, tap to click, double tap to double-click, two fingers to scroll, and so on.

Status: **Phases 0–3 implemented (pending on-device tuning); air tap deferred; scroll inertia not done.** Decided: Windows first, Python + MediaPipe. Still open (before Phase 2): click default, right-click gesture, camera, handedness.

---

## 1. Goals and non-goals

**Goals**
- Webcam-only: no special hardware.
- Usable as a daily mouse replacement for basic work: point, click, double-click, right-click, scroll, drag.
- Low latency (end-to-end < 50 ms on a mid-range laptop, 30 FPS or better).
- Few false clicks. A missed click is annoying; an accidental click can be destructive.
- Cross-platform in design (Windows, macOS, Linux), with Windows/macOS first.

**Non-goals (v1)**
- Keyboard replacement or text entry.
- Multi-user or multi-hand-as-two-cursors support.
- Depth cameras or wearables.
- Gaming-grade precision.

---

## 2. Gesture vocabulary (proposed)

| Action | Gesture | Notes |
|---|---|---|
| Move cursor | Index finger extended, other fingers curled | Index fingertip drives the cursor |
| Single click | **Air tap**: quick forward jab of the index finger | Fallback: pinch thumb + index and release (see risk R1) |
| Double click | Two taps within ~350 ms | Timing window configurable |
| Right click | Middle finger tap (index + middle up, quick tap) or thumb + middle pinch | **[DECIDE]** |
| Scroll | **Two fingers** (index + middle extended, together) moving up/down | Left/right for horizontal scroll |
| Drag and drop | Pinch (thumb + index) and hold, move, release to drop | Also covers text selection |
| Pause / idle | Open palm, or hand out of frame | Cursor freezes; prevents stray input |
| Re-enable / lock toggle | Hold a fist for ~1 s | Safety switch |
| Zoom (later) | Pinch spread with two hands, or Ctrl+scroll mapping | Phase 5 |

Principle: gestures must be **distinct in hand shape** (finger count / pose), so a pose classifier picks the *mode* and motion within the mode picks the *action*.

---

## 3. Technical approach

### Stack
- **Language:** Python 3.10+ for v1. Fast to iterate, the best hand-tracking ecosystem. A later port to Rust/C++ is possible if performance requires it.
- **Camera:** OpenCV (`cv2.VideoCapture`), threaded capture so the latest frame is always used (no queue lag).
- **Hand tracking:** MediaPipe Hands / Hand Landmarker (21 landmarks per hand, runs real-time on CPU).
- **OS input injection:** `pynput` or `pyautogui` behind a thin `InputBackend` interface, so platform-specific backends (Win32 `SendInput`, macOS Quartz, Linux uinput/XTest) can be swapped in.
- **Smoothing:** One Euro Filter (the standard for jitter versus lag in pointer input).
- **Config/UI:** YAML/TOML config, a small debug overlay window (landmarks + current gesture), system tray later.
- **Tooling:** `pytest`, `ruff`, `mypy`, `uv` or `pip-tools`, GitHub Actions CI.

### Pipeline

```
Camera ─▶ HandTracker ─▶ FeatureExtractor ─▶ GestureEngine ─▶ ActionMapper ─▶ InputBackend
(frames)  (21 landmarks)  (finger states,    (state machine,   (click/scroll/   (OS mouse
                           velocities,        debouncing,       move events)     events)
                           pinch dist)        timing)
                                  │
                                  └──▶ CursorMapper (active region → screen coords, One Euro smoothing)
```

Key design rule: **everything after `HandTracker` is pure logic with no camera or OS dependency**, so it can be unit-tested by replaying recorded landmark sequences (JSON). This also matters because CI and this dev container have no webcam or display.

### Proposed layout

```
aircursor/
  capture/        # threaded camera source, file/replay source
  tracking/       # MediaPipe wrapper, Landmarks dataclass
  features/       # finger up/down, pinch distance, velocity, hand scale
  gestures/       # pose classifier + state machine (tap, double tap, scroll, drag)
  cursor/         # active-region mapping, One Euro filter, acceleration curve
  actions/        # InputBackend interface + win/mac/linux implementations
  ui/             # debug overlay, tray, calibration wizard
  config/         # defaults + user config loading
tests/            # replay-based gesture tests, filter tests
recordings/       # sample landmark sequences for tests
docs/
```

---

## 4. Hard problems and risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | **Air tap is hard with one 2D camera.** Forward motion shows up as a small change in z estimate, fingertip scale, and a brief downward y-shift, and all of these are noisy. | Detect the tap from a combination of signals (z-velocity, finger-length foreshortening, short downward jab). Collect real recordings and tune thresholds. Ship **pinch-to-click as a built-in alternative mode**, and let the user choose in config. Decide the default after Phase 2 testing. |
| R2 | **Cursor moves during the tap**, so the click lands on the wrong spot. | Keep a ~150 ms ring buffer of cursor positions. When a tap is confirmed, click at the position from *before* the tap motion began, and freeze the cursor for a short lock window. |
| R3 | **Jitter versus lag.** Raw landmarks shake. Heavy smoothing feels laggy. | One Euro Filter, with `min_cutoff` and `beta` tunable. Add a small dead zone when the hand is almost still. |
| R4 | **Accidental clicks and scrolls** (talking with your hands, reaching for the mouse). | Pose-gated modes, an activation hysteresis (a pose must be held for N frames), the open-palm pause, and the fist lock toggle. |
| R5 | **Arm fatigue** ("gorilla arm"). | Small active region (the user reaches only about 1/3 of the frame), relative/clutch mode (lift hand to re-center), and rest-friendly defaults. |
| R6 | **Lighting, backgrounds, occlusion, and hand-edge-of-frame loss.** | Rely on MediaPipe robustness, show a "hand lost" indicator, and add a low-light tip to the docs. |
| R7 | **Latency** from capture, inference, and smoothing. | Threaded capture with latest-frame only, a lite model, reduced resolution (e.g. 640×480), profile each stage, and set a latency budget per stage. |
| R8 | **OS permissions and display servers.** macOS needs Accessibility and Camera permission. Linux Wayland blocks synthetic input, so it needs uinput or the X11 session. | A `doctor` command that checks permissions. A documented Wayland workaround. |
| R9 | Multiple hands or a hand-over-hand cross. | Track only the primary hand (the first one that makes a valid pose, or the right/left preference from config). |
| R10 | Dev environment has no webcam. | Replay-driven tests and a recorded-video source. Real-device tuning must be done on the user's machine. |

---

## 5. Roadmap

Each phase ends with something runnable and demonstrable.

### Phase 0 — Foundations (½–1 day) ✅
- Repo scaffold, `pyproject.toml`, lint/type/test tooling, CI.
- `HandTracker` + a debug window that draws landmarks from the webcam or a video file.
- **Exit:** landmarks visible live, with FPS counter.

### Phase 1 — Point and move (1–2 days) ✅
- Finger-pose classification (which fingers are up).
- Active-region → screen mapping, One Euro smoothing, optional acceleration.
- `InputBackend` for Windows and macOS (move only).
- Pause on open palm / hand lost.
- **Exit:** cursor follows the index finger smoothly and freezes when the hand drops.

### Phase 2 — Click and double click (2–4 days) ← pinch click done; air tap not started
- Record a dataset of taps, pinches, and non-tap motions (landmark JSON) to tune against.
- Implement the tap detector, the position-rewind and cursor-lock logic (R2), and the double-tap timer.
- Implement pinch-click as the alternative mode.
- Replay tests with precision/recall targets (e.g. ≥95% detection, <1 false click per 5 minutes of normal use).
- **Exit:** reliable left click and double click in either mode.

### Phase 3 — Scroll, right click, drag (2–3 days) ✅ (right click = thumb + middle pinch; no inertia yet)
- Two-finger scroll with velocity-to-delta mapping, inertia, and a dead zone.
- Right click gesture.
- Pinch-hold drag/drop.
- **Exit:** can browse a web page and move a file or select text hands-free.

### Phase 4 — Polish and safety (2–3 days)
- Fist lock toggle, a visible status overlay (current mode, locked or not), audio or visual click feedback.
- Calibration wizard (set the active region and the user's reach).
- Config file with per-gesture sensitivity, and left-handed mode.
- Linux backend and a `doctor` command.
- **Exit:** usable for a full work session without surprise input.

### Phase 5 — Extras (optional, later)
- Zoom and pinch-spread, virtual desktop swipe, media controls.
- A learned gesture classifier if the heuristics hit a ceiling.
- Tray app and an installer/packaging (PyInstaller or similar).
- Port the hot path to a compiled language if latency demands it.

---

## 6. Testing strategy

- **Unit tests:** One Euro filter, finger-state features, coordinate mapping.
- **Replay tests:** recorded landmark JSON → `GestureEngine` → assert the exact event sequence (`CLICK`, `DOUBLE_CLICK`, `SCROLL(dy)`, ...). Include negative recordings (hand waving, talking with hands, reaching) that must produce **no** clicks.
- **Fake `InputBackend`** records emitted events for assertions.
- **Latency benchmark script** reporting per-stage timings.
- **Manual QA checklist** for real-device tuning (lighting, distance, handedness).

---

## 7. Open questions for you

1. **[DECIDE] Platforms:** Windows, macOS, or Linux first? (Affects the first `InputBackend`.)
2. **[DECIDE] Language/stack:** Python + MediaPipe (recommended for v1), or something else (e.g. a Rust/JS web-based version)?
3. **[DECIDE] Click default:** Do you want the air tap as the default regardless, or should we default to the more reliable pinch click if tap detection proves flaky in Phase 2?
4. **[DECIDE] Right-click gesture:** Middle-finger tap, thumb + middle pinch, or something else?
5. **Camera:** Built-in laptop webcam, or an external one (mounted above or in front of the screen)?
6. **Hand:** Right hand, left hand, or either?
7. **Scope for v1:** Is Phase 0–3 enough for the first release, or do you want the calibration, tray app, and Linux support before calling it v1?
