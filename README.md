# Genesis Head Tracker

A lightweight, cross-platform (**Windows & Linux**) 6-DOF head tracker powered by **MediaPipe Face Landmarker** and a **200 Hz One-Euro interpolated OpenTrack UDP** stream (`127.0.0.1:4248`).

Designed for **Euro Truck Simulator 2**, **American Truck Simulator** (including **Project Ultimate App**), and any game or flight/racing sim supporting OpenTrack UDP.

## Features
- **Cross-platform:** Works natively on **Windows** (Media Foundation / DirectShow + optional USB Android camera via `scrcpy`) and **Linux** (V4L2 webcams).
- **200 Hz Smooth Output:** Decoupled 200 Hz UDP interpolation thread + adaptive **One-Euro filter** for zero-jitter gauges and instant mirror checks.
- **Simple Dark UI:** Camera selector, live preview, 90° rotation, **Smoothness / Sensitivity / Center Deadzone** sliders, and live `config.json` hot-reload.
- **Global Hotkeys:** `F7` to recenter, `Scroll Lock` to pause/resume while in-game.

## Quick Start

### Windows
1. Install [uv](https://docs.astral.sh/uv/).
2. Run `start_headtrack.bat` (or `uv run python headtrack.py`).
   - On first launch, `face_landmarker.task` is downloaded automatically.

### Linux
1. Install [uv](https://docs.astral.sh/uv/) and ensure Python Tkinter is installed (e.g. `sudo apt install python3-tk` on Ubuntu/Debian).
2. Make the launcher executable and run it:
   ```bash
   chmod +x start_headtrack.sh
   ./start_headtrack.sh
   ```

## Configuration (`config.json`)
- Edit `config.json` anytime—changes to `axes` and `filter` hot-reload live while the app is running.
- Default UDP target: `127.0.0.1:4248` (`<6d`: `x, y, z, yaw, pitch, roll`).
