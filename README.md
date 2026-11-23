# Genesis Head Tracker

A lightweight, cross-platform (**Windows & Linux**) 6-DOF head tracker powered by **MediaPipe Face Landmarker** and a **200 Hz One-Euro interpolated OpenTrack UDP** stream (`127.0.0.1:4248`).

Designed for **any sim or game** supporting OpenTrack UDP or TrackIR/FreeTrack (**Microsoft Flight Simulator, DCS World, iRacing, Assetto Corsa, BeamNG.drive, Star Citizen, Elite Dangerous, Euro Truck Simulator 2, American Truck Simulator**, etc.).

- **Direct UDP games & plugins:** Works straight out of the box with any game or plugin accepting OpenTrack UDP on `127.0.0.1:4248`.
- **Any TrackIR / FreeTrack game** (MSFS, DCS World, iRacing, Assetto Corsa, BeamNG.drive, Star Citizen, Elite Dangerous, Euro Truck Simulator 2, American Truck Simulator, Farming Simulator, Arma, etc.):
  1. Open **OpenTrack**.
  2. Set **Input** to **`UDP over network`** (port `4248`).
  3. Set **Output** to **`freetrack 2.0 Enhanced`**.
  4. Set **Filter** to **`None`** (so Genesis Head Tracker's 200 Hz One-Euro smoothing handles everything) and click **Start**.

## Features
- **Cross-platform:** Works natively on **Windows** (Media Foundation / DirectShow + optional USB Android camera via `scrcpy`) and **Linux** (V4L2 webcams).
- **200 Hz Smooth Output:** Decoupled 200 Hz UDP interpolation thread + adaptive **One-Euro filter** for zero-jitter gauges and instant mirror checks.
- **Truck Window Look-Out:** Expanded **Max Look Angle** slider (`90°–175°`, default `155°`) and optional **Truck Window Lean-Out** that smoothly blends lateral `X` shift once you look past `65°` yaw—making side-window checks and trailer backing effortless while keeping normal mirror checks centered.
- **Simple Dark UI:** Camera selector, live preview, 90° rotation, **Smoothness / Sensitivity / Center Deadzone / Max Look Angle** sliders, **Truck Window Lean-Out** toggle, and live `config.json` hot-reload.
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
