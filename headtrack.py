"""Genesis Head Tracker: Cross-platform 6-DOF MediaPipe head tracker (Windows & Linux)."""

from __future__ import annotations

import json
import math
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import customtkinter as ctk
import cv2
import mediapipe as mp
import numpy as np
from cv2_enumerate_cameras import enumerate_cameras
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from PIL import Image, ImageTk
from pynput import keyboard

IS_FROZEN = getattr(sys, "frozen", False)
APP_DIR = (Path.home() / ".genesis-head-tracker") if IS_FROZEN else Path(__file__).resolve().parent
APP_DIR.mkdir(parents=True, exist_ok=True)
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
MODEL_PATH = APP_DIR / "face_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
CONFIG_PATH = APP_DIR / "config.json"
ICON_ICO = RESOURCE_DIR / "assets" / "icon.ico"
ICON_PNG = RESOURCE_DIR / "assets" / "icon.png"
IS_WINDOWS = sys.platform == "win32"

DEFAULT_CONFIG = {
    "camera_source": "",
    "rotate": 0,
    "udp_ip": "127.0.0.1",
    "udp_port": 4248,
    "udp_hz": 200,
    "recenter_key": "f7",
    "pause_key": "scroll_lock",
    "window_lean": {"enabled": True, "start_yaw": 65.0, "full_yaw": 125.0, "max_x": 18.0, "invert": False},
    "filter": {"min_cutoff": 0.75, "beta": 0.025, "d_cutoff": 1.0, "output_lerp": 0.18},
    "axes": {
        "yaw":   {"scale": 1.9, "deadzone": 1.4, "curve": 1.32, "max": 155.0, "invert": False},
        "pitch": {"scale": 1.4, "deadzone": 1.2, "curve": 1.25, "max": 55.0, "invert": True},
        "roll":  {"scale": 0.5, "deadzone": 2.0, "curve": 1.20, "max": 25.0, "invert": False},
        "x":     {"scale": 1.2, "deadzone": 0.8, "curve": 1.15, "max": 35.0, "invert": False},
        "y":     {"scale": 0.7, "deadzone": 0.8, "curve": 1.15, "max": 15.0, "invert": False},
        "z":     {"scale": 0.8, "deadzone": 1.0, "curve": 1.15, "max": 20.0, "invert": False},
    },
}

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    SCRCPY_EXE = Path(r"C:\Users\Coraj\Downloads\scrcpy-win64-v4.0\scrcpy-win64-v4.0\scrcpy.exe")
    SCRCPY_TITLE = "HeadTrackPhoneCam"
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class ScrcpyCameraCapture:
        """Windows helper: spawns scrcpy --video-source=camera and captures via PrintWindow."""

        def __init__(self, camera_id: int = 1, fps: int = 30) -> None:
            self.camera_id = camera_id
            self.fps = fps
            self.proc: subprocess.Popen | None = None
            self.hwnd: int = 0
            self._start()

        def _start(self) -> None:
            old_hwnd = user32.FindWindowW(None, SCRCPY_TITLE)
            if old_hwnd:
                user32.PostMessageW(old_hwnd, 0x0010, 0, 0)
                time.sleep(0.2)

            cmd = [
                str(SCRCPY_EXE),
                "--video-source=camera",
                f"--camera-id={self.camera_id}",
                "--camera-size=640x480",
                f"--camera-fps={self.fps}",
                "--no-audio",
                "--window-borderless",
                f"--window-title={SCRCPY_TITLE}",
                "--window-x=40",
                "--window-y=40",
                "--window-width=320",
                "--window-height=240",
            ]
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            for _ in range(50):
                self.hwnd = user32.FindWindowW(None, SCRCPY_TITLE)
                if self.hwnd:
                    ex_style = user32.GetWindowLongW(self.hwnd, -20)
                    user32.SetWindowLongW(self.hwnd, -20, (ex_style | 0x00000080) & ~0x00040000)
                    user32.SetWindowPos(self.hwnd, 1, 0, 0, 0, 0, 0x0013)
                    break
                time.sleep(0.1)

        def read(self) -> tuple[bool, np.ndarray | None]:
            if self.proc is not None and self.proc.poll() is not None:
                return False, None
            if not self.hwnd:
                self.hwnd = user32.FindWindowW(None, SCRCPY_TITLE)
                if not self.hwnd:
                    return False, None

            rect = wintypes.RECT()
            if not user32.GetWindowRect(self.hwnd, ctypes.byref(rect)):
                return False, None
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w <= 16 or h <= 16:
                return False, None

            hwnd_dc = user32.GetWindowDC(self.hwnd)
            if not hwnd_dc:
                return False, None
            mfc_dc = gdi32.CreateCompatibleDC(hwnd_dc)
            bmp = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
            gdi32.SelectObject(mfc_dc, bmp)
            ok = user32.PrintWindow(self.hwnd, mfc_dc, 2)
            frame = None
            if ok:
                bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
                buf = np.zeros((h, w, 4), dtype=np.uint8)
                gdi32.GetDIBits(mfc_dc, bmp, 0, h, buf.ctypes.data_as(ctypes.c_void_p), ctypes.byref(bi), 0)
                frame = np.ascontiguousarray(buf[:, :, :3])
            gdi32.DeleteObject(bmp)
            gdi32.DeleteDC(mfc_dc)
            user32.ReleaseDC(self.hwnd, hwnd_dc)
            if frame is None or frame.max() == 0:
                return False, None
            return True, frame

        def release(self) -> None:
            if self.proc is not None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                self.proc = None


def ensure_model() -> None:
    if not MODEL_PATH.exists():
        print(f"Downloading {MODEL_PATH.name}...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)


class LowPassFilter:
    def __init__(self, alpha: float = 1.0) -> None:
        self._alpha = alpha
        self._initialized = False
        self._y = 0.0

    def apply(self, value: float, alpha: float | None = None) -> float:
        if alpha is not None:
            self._alpha = alpha
        if not self._initialized:
            self._y = value
            self._initialized = True
        else:
            self._y = self._alpha * value + (1.0 - self._alpha) * self._y
        return self._y

    def reset(self) -> None:
        self._initialized = False


class OneEuroFilter:
    def __init__(self, min_cutoff: float = 0.75, beta: float = 0.025, d_cutoff: float = 1.0) -> None:
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._x_filter = LowPassFilter()
        self._dx_filter = LowPassFilter()
        self._last_time: float | None = None
        self._last_x: float = 0.0

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def apply(self, x: float, timestamp: float) -> float:
        if self._last_time is None:
            self._last_time = timestamp
            self._last_x = x
            self._dx_filter.apply(0.0, 1.0)
            return self._x_filter.apply(x, 1.0)
        dt = max(timestamp - self._last_time, 1e-4)
        self._last_time = timestamp
        dx = (x - self._last_x) / dt
        self._last_x = x
        edx = self._dx_filter.apply(dx, self._alpha(self.d_cutoff, dt))
        cutoff = self.min_cutoff + self.beta * abs(edx)
        return self._x_filter.apply(x, self._alpha(cutoff, dt))

    def reset(self) -> None:
        self._last_time = None
        self._x_filter.reset()
        self._dx_filter.reset()


def shape_axis(value: float, cfg: dict) -> float:
    if cfg.get("invert", False):
        value = -value
    deadzone = float(cfg.get("deadzone", 0.0))
    if abs(value) <= deadzone:
        return 0.0
    sign = 1.0 if value > 0 else -1.0
    trimmed = abs(value) - deadzone
    curve = float(cfg.get("curve", 1.0))
    scale = float(cfg.get("scale", 1.0))
    limit = float(cfg.get("max", 180.0))
    shaped = sign * (trimmed ** curve) * scale
    return max(-limit, min(limit, shaped))


def apply_window_lean(out: list[float], lean_cfg: dict, x_cfg: dict) -> list[float]:
    """Smoothly blend lateral X shift when yaw turns past start_yaw (truck window look-out)."""
    if not lean_cfg.get("enabled", True):
        return out
    yaw = out[3]
    start_yaw = float(lean_cfg.get("start_yaw", 65.0))
    full_yaw = max(start_yaw + 1.0, float(lean_cfg.get("full_yaw", 125.0)))
    max_x = float(lean_cfg.get("max_x", 18.0))
    abs_yaw = abs(yaw)
    if abs_yaw <= start_yaw or max_x <= 0.0:
        return out
    t = min(1.0, (abs_yaw - start_yaw) / (full_yaw - start_yaw))
    smooth_t = t * t * (3.0 - 2.0 * t)
    direction = 1.0 if yaw > 0 else -1.0
    if lean_cfg.get("invert", False):
        direction = -direction
    x_limit = max(float(x_cfg.get("max", 35.0)), max_x)
    out[0] = max(-x_limit, min(x_limit, out[0] + direction * smooth_t * max_x))
    return out


def matrix_to_pose(mat: np.ndarray) -> tuple[float, float, float, float, float, float]:
    tx, ty, tz = float(mat[0, 3]), float(mat[1, 3]), float(mat[2, 3])
    rot = mat[:3, :3].astype(np.float64)
    sy = math.sqrt(rot[0, 0] * rot[0, 0] + rot[1, 0] * rot[1, 0])
    if sy > 1e-6:
        pitch = math.degrees(math.atan2(rot[2, 1], rot[2, 2]))
        yaw = math.degrees(math.atan2(-rot[2, 0], sy))
        roll = math.degrees(math.atan2(rot[1, 0], rot[0, 0]))
    else:
        pitch = math.degrees(math.atan2(-rot[1, 2], rot[1, 1]))
        yaw = math.degrees(math.atan2(-rot[2, 0], sy))
        roll = 0.0
    return tx, ty, -tz, -yaw, pitch, -roll


def parse_key(name: str) -> keyboard.Key | keyboard.KeyCode | None:
    name = name.strip().lower()
    if hasattr(keyboard.Key, name):
        return getattr(keyboard.Key, name)
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name)
    return None


def list_sources() -> dict[str, str | int]:
    sources: dict[str, str | int] = {}
    if IS_WINDOWS and SCRCPY_EXE.exists():
        sources["Phone Front Camera (USB)"] = "scrcpy:1:30"
        sources["Phone Back Camera 60 FPS (USB)"] = "scrcpy:0:60"
    for c in enumerate_cameras():
        if IS_WINDOWS:
            backend_tag = "MSMF" if c.index >= 1400 else "DSHOW"
            label = f"{c.name} ({backend_tag})"
        else:
            label = f"{c.name} (#{c.index})"
        if label not in sources:
            sources[label] = c.index
    if not sources:
        sources["Default Camera (0)"] = 0
    return sources


class GenesisHeadTrackerApp(ctk.CTk):
    def __init__(self, cfg: dict) -> None:
        super().__init__()
        self.cfg = cfg
        self.title("Genesis Head Tracker")
        self.geometry("760x500")
        self.minsize(720, 480)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        if IS_WINDOWS and ICON_ICO.exists():
            self.iconbitmap(str(ICON_ICO))
        elif ICON_PNG.exists():
            self._icon_photo = ImageTk.PhotoImage(file=str(ICON_PNG))
            self.iconphoto(True, self._icon_photo)

        self.lock = threading.Lock()
        self.running = True
        self.paused = False
        self.recenter_requested = True
        self.rotate_deg = int(cfg.get("rotate", 0)) % 360
        self.zero = [0.0] * 6
        self.target_out = [0.0] * 6
        self.smooth_out = [0.0] * 6
        self.latest_rgb: np.ndarray | None = None
        self.status_text = "STARTING CAMERA..."
        self.status_color = "#f59e0b"
        self.fps_val = 0.0
        self._cfg_mtime = CONFIG_PATH.stat().st_mtime if CONFIG_PATH.exists() else 0.0

        self.sources = list_sources()
        saved_src = str(cfg.get("camera_source", ""))
        if saved_src not in self.sources:
            saved_src = next(iter(self.sources.keys()))
        self.current_source_label = saved_src
        self.cap = None

        self._build_ui()
        self._init_tracker()
        self._start_threads()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(30, self._update_ui)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, corner_radius=12)
        left.grid(row=0, column=0, padx=(14, 7), pady=14, sticky="nsew")
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        self.status_lbl = ctk.CTkLabel(left, text="STARTING CAMERA...", font=ctk.CTkFont(size=15, weight="bold"), text_color="#f59e0b")
        self.status_lbl.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")

        self.video_lbl = ctk.CTkLabel(left, text="", fg_color="#111111", corner_radius=8)
        self.video_lbl.grid(row=1, column=0, padx=12, pady=6, sticky="nsew")

        self.pose_lbl = ctk.CTkLabel(left, text="Yaw: +0.0°   Pitch: +0.0°   Roll: +0.0°", font=ctk.CTkFont(family="Consolas", size=13))
        self.pose_lbl.grid(row=2, column=0, padx=12, pady=(4, 10))

        right = ctk.CTkFrame(self, corner_radius=12)
        right.grid(row=0, column=1, padx=(7, 14), pady=14, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="Camera Source", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, padx=14, pady=(12, 2), sticky="w")
        labels = list(self.sources.keys())
        self.cam_menu = ctk.CTkOptionMenu(right, values=labels, command=self._on_camera_change)
        self.cam_menu.set(self.current_source_label)
        self.cam_menu.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="ew")

        btn_row = ctk.CTkFrame(right, fg_color="transparent")
        btn_row.grid(row=2, column=0, padx=14, pady=4, sticky="ew")
        btn_row.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(btn_row, text="Recenter (F7)", command=self._recenter, height=34).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        self.pause_btn = ctk.CTkButton(btn_row, text="Pause", command=self._toggle_pause, height=34, fg_color="#374151")
        self.pause_btn.grid(row=0, column=1, padx=4, sticky="ew")
        ctk.CTkButton(btn_row, text="Rotate 90°", command=self._rotate, height=34, fg_color="#374151").grid(row=0, column=2, padx=(4, 0), sticky="ew")

        flt = self.cfg.get("filter", {})
        axes = self.cfg.get("axes", {})
        lean_cfg = self.cfg.setdefault("window_lean", dict(DEFAULT_CONFIG["window_lean"]))
        smooth_init = max(0.05, min(1.0, 1.0 - float(flt.get("output_lerp", 0.18)) * 2.0))
        sens_init = float(axes.get("yaw", {}).get("scale", 1.9))
        dz_init = float(axes.get("yaw", {}).get("deadzone", 1.4))
        max_yaw_init = max(90.0, min(175.0, float(axes.get("yaw", {}).get("max", 155.0))))
        lean_enabled = bool(lean_cfg.get("enabled", True))

        self.smooth_lbl = ctk.CTkLabel(right, text=f"Smoothness: {smooth_init:.2f}")
        self.smooth_lbl.grid(row=3, column=0, padx=14, pady=(10, 0), sticky="w")
        self.smooth_slider = ctk.CTkSlider(right, from_=0.1, to=0.95, command=self._on_smooth_change)
        self.smooth_slider.set(smooth_init)
        self.smooth_slider.grid(row=4, column=0, padx=14, pady=(2, 4), sticky="ew")

        self.sens_lbl = ctk.CTkLabel(right, text=f"Sensitivity: {sens_init:.2f}x")
        self.sens_lbl.grid(row=5, column=0, padx=14, pady=(4, 0), sticky="w")
        self.sens_slider = ctk.CTkSlider(right, from_=0.6, to=3.0, command=self._on_sens_change)
        self.sens_slider.set(sens_init)
        self.sens_slider.grid(row=6, column=0, padx=14, pady=(2, 4), sticky="ew")

        self.dz_lbl = ctk.CTkLabel(right, text=f"Center Deadzone: {dz_init:.1f}°")
        self.dz_lbl.grid(row=7, column=0, padx=14, pady=(4, 0), sticky="w")
        self.dz_slider = ctk.CTkSlider(right, from_=0.0, to=3.5, command=self._on_dz_change)
        self.dz_slider.set(dz_init)
        self.dz_slider.grid(row=8, column=0, padx=14, pady=(2, 4), sticky="ew")

        self.max_yaw_lbl = ctk.CTkLabel(right, text=f"Max Look Angle: {max_yaw_init:.0f}°")
        self.max_yaw_lbl.grid(row=9, column=0, padx=14, pady=(4, 0), sticky="w")
        self.max_yaw_slider = ctk.CTkSlider(right, from_=90.0, to=175.0, command=self._on_max_yaw_change)
        self.max_yaw_slider.set(max_yaw_init)
        self.max_yaw_slider.grid(row=10, column=0, padx=14, pady=(2, 6), sticky="ew")

        self.lean_var = ctk.BooleanVar(value=lean_enabled)
        self.lean_chk = ctk.CTkCheckBox(
            right,
            text="Truck Window Lean-Out",
            variable=self.lean_var,
            command=self._on_lean_toggle,
        )
        self.lean_chk.grid(row=11, column=0, padx=14, pady=(4, 6), sticky="w")

        udp_ip = self.cfg.get("udp_ip", "127.0.0.1")
        udp_port = self.cfg.get("udp_port", 4248)
        ctk.CTkLabel(right, text=f"UDP -> {udp_ip}:{udp_port} (200 Hz)", font=ctk.CTkFont(size=12), text_color="#9ca3af").grid(row=12, column=0, padx=14, pady=(4, 10), sticky="w")

    def _init_tracker(self) -> None:
        ensure_model()
        base_options = mp_python.BaseOptions(model_asset_path=str(MODEL_PATH))
        options = mp_vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.VIDEO,
            num_faces=1,
            output_facial_transformation_matrixes=True,
            min_face_detection_confidence=0.45,
            min_face_presence_confidence=0.4,
            min_tracking_confidence=0.35,
        )
        self.landmarker = mp_vision.FaceLandmarker.create_from_options(options)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_addr = (str(self.cfg.get("udp_ip", "127.0.0.1")), int(self.cfg.get("udp_port", 4248)))
        self.axis_names = ("x", "y", "z", "yaw", "pitch", "roll")
        flt = self.cfg.get("filter", {})
        self.filters = {
            k: OneEuroFilter(
                min_cutoff=float(flt.get("min_cutoff", 0.75)),
                beta=float(flt.get("beta", 0.025)),
                d_cutoff=float(flt.get("d_cutoff", 1.0)),
            )
            for k in self.axis_names
        }
        self.output_lerp = max(0.03, min(1.0, float(flt.get("output_lerp", 0.18))))
        self.recenter_key = parse_key(str(self.cfg.get("recenter_key", "f7")))
        self.pause_key = parse_key(str(self.cfg.get("pause_key", "scroll_lock")))
        self.listener = keyboard.Listener(on_press=self._on_global_key)
        self.listener.start()

    def _on_global_key(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        with self.lock:
            if self.recenter_key is not None and key == self.recenter_key:
                self.recenter_requested = True
            elif self.pause_key is not None and key == self.pause_key:
                self.paused = not self.paused

    def _recenter(self) -> None:
        with self.lock:
            self.recenter_requested = True

    def _toggle_pause(self) -> None:
        with self.lock:
            self.paused = not self.paused
            p = self.paused
        self.pause_btn.configure(text="Resume" if p else "Pause")

    def _rotate(self) -> None:
        with self.lock:
            self.rotate_deg = (self.rotate_deg + 90) % 360
            self.cfg["rotate"] = self.rotate_deg

    def _on_camera_change(self, label: str) -> None:
        with self.lock:
            self.current_source_label = label
            self.cfg["camera_source"] = label

    def _on_smooth_change(self, val: float) -> None:
        self.smooth_lbl.configure(text=f"Smoothness: {val:.2f}")
        lerp = max(0.04, min(0.5, (1.0 - val) * 0.5))
        min_cut = max(0.3, (1.0 - val) * 2.0)
        with self.lock:
            self.output_lerp = lerp
            for f in self.filters.values():
                f.min_cutoff = min_cut
            self.cfg.setdefault("filter", {})["output_lerp"] = round(lerp, 3)
            self.cfg["filter"]["min_cutoff"] = round(min_cut, 3)

    def _on_sens_change(self, val: float) -> None:
        self.sens_lbl.configure(text=f"Sensitivity: {val:.2f}x")
        with self.lock:
            axes = self.cfg.setdefault("axes", {})
            axes.setdefault("yaw", {})["scale"] = round(val, 2)
            axes.setdefault("pitch", {})["scale"] = round(val * 0.8, 2)

    def _on_dz_change(self, val: float) -> None:
        self.dz_lbl.configure(text=f"Center Deadzone: {val:.1f}°")
        with self.lock:
            axes = self.cfg.setdefault("axes", {})
            axes.setdefault("yaw", {})["deadzone"] = round(val, 2)
            axes.setdefault("pitch", {})["deadzone"] = round(val * 0.85, 2)

    def _on_max_yaw_change(self, val: float) -> None:
        self.max_yaw_lbl.configure(text=f"Max Look Angle: {val:.0f}°")
        with self.lock:
            axes = self.cfg.setdefault("axes", {})
            axes.setdefault("yaw", {})["max"] = round(val, 1)

    def _on_lean_toggle(self) -> None:
        enabled = bool(self.lean_var.get())
        with self.lock:
            self.cfg.setdefault("window_lean", dict(DEFAULT_CONFIG["window_lean"]))["enabled"] = enabled

    def _start_threads(self) -> None:
        threading.Thread(target=self._camera_loop, daemon=True).start()
        threading.Thread(target=self._udp_loop, daemon=True).start()

    def _udp_loop(self) -> None:
        interval = 1.0 / max(60, int(self.cfg.get("udp_hz", 200)))
        while True:
            t0 = time.perf_counter()
            with self.lock:
                if not self.running:
                    break
                lerp = self.output_lerp
                for i in range(6):
                    self.smooth_out[i] += (self.target_out[i] - self.smooth_out[i]) * lerp
                pkt = struct.pack("<6d", *self.smooth_out)
            self.sock.sendto(pkt, self.udp_addr)
            dt = time.perf_counter() - t0
            if dt < interval:
                time.sleep(interval - dt)

    def _open_source(self, spec: str | int):
        if IS_WINDOWS and isinstance(spec, str) and spec.startswith("scrcpy:"):
            _, cam_id, fps = spec.split(":")
            return ScrcpyCameraCapture(camera_id=int(cam_id), fps=int(fps))
        cap = cv2.VideoCapture(int(spec))
        cap.set(cv2.CAP_PROP_FPS, 60)
        return cap

    def _camera_loop(self) -> None:
        t0 = time.perf_counter()
        fps_c = 0
        fps_t = t0
        active_label = ""
        last_ts_ms = -1
        while True:
            with self.lock:
                if not self.running:
                    break
                want_label = self.current_source_label
                rot = self.rotate_deg
                paused = self.paused

            if self.cap is None or active_label != want_label:
                if self.cap is not None:
                    self.cap.release()
                with self.lock:
                    self.status_text = f"CONNECTING {want_label}..."
                    self.status_color = "#f59e0b"
                self.cap = self._open_source(self.sources[want_label])
                active_label = want_label

            ok, frame = self.cap.read()
            if not ok or frame is None:
                time.sleep(0.02)
                continue

            if rot == 90:
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            elif rot == 180:
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            elif rot == 270:
                frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

            is_blank = (frame[:, :, 0].max() == 0 and frame[:, :, 2].max() == 0)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            now = time.perf_counter()

            if is_blank:
                status, color = "BLANK VIDEO (Check Camera)", "#f59e0b"
            elif paused:
                status, color = "PAUSED", "#38bdf8"
            else:
                ts_ms = max(last_ts_ms + 1, int((now - t0) * 1000.0))
                last_ts_ms = ts_ms
                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                res = self.landmarker.detect_for_video(mp_img, ts_ms)
                if res.facial_transformation_matrixes:
                    raw = matrix_to_pose(np.asarray(res.facial_transformation_matrixes[0]))
                    with self.lock:
                        if self.recenter_requested:
                            self.zero = list(raw)
                            for f in self.filters.values():
                                f.reset()
                            self.recenter_requested = False
                        zero = self.zero
                        axes_cfg = self.cfg.get("axes", {})
                        lean_cfg = self.cfg.get("window_lean", DEFAULT_CONFIG["window_lean"])
                    centered = [raw[i] - zero[i] for i in range(6)]
                    filtered = [self.filters[self.axis_names[i]].apply(centered[i], now) for i in range(6)]
                    out = [shape_axis(filtered[i], axes_cfg.get(self.axis_names[i], {})) for i in range(6)]
                    out = apply_window_lean(out, lean_cfg, axes_cfg.get("x", {}))
                    with self.lock:
                        self.target_out = out
                    status, color = "TRACKING", "#22c55e"
                else:
                    status, color = "NO FACE (Click Rotate 90°)", "#ef4444"

            fps_c += 1
            if now - fps_t >= 0.5:
                self.fps_val = fps_c / (now - fps_t)
                fps_c = 0
                fps_t = now

            with self.lock:
                self.latest_rgb = rgb
                self.status_text = f"{status}  |  {self.fps_val:.0f} FPS"
                self.status_color = color

    def _update_ui(self) -> None:
        try:
            mtime = CONFIG_PATH.stat().st_mtime
            if mtime > self._cfg_mtime:
                self._cfg_mtime = mtime
                new_cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                with self.lock:
                    self.cfg["axes"] = new_cfg.get("axes", self.cfg.get("axes", {}))
                    if "window_lean" in new_cfg:
                        self.cfg["window_lean"] = new_cfg["window_lean"]
                    flt = new_cfg.get("filter", {})
                    self.cfg["filter"] = flt
                    self.output_lerp = max(0.03, min(1.0, float(flt.get("output_lerp", self.output_lerp))))
                    for f in self.filters.values():
                        f.min_cutoff = float(flt.get("min_cutoff", f.min_cutoff))
                        f.beta = float(flt.get("beta", f.beta))
        except Exception:
            pass

        with self.lock:
            if not self.running:
                return
            rgb = self.latest_rgb
            st = self.status_text
            col = self.status_color
            out = list(self.smooth_out)
            paused = self.paused

        self.status_lbl.configure(text=st, text_color=col)
        self.pose_lbl.configure(text=f"Yaw: {out[3]:+5.1f}°   Pitch: {out[4]:+5.1f}°   Roll: {out[5]:+5.1f}°")
        self.pause_btn.configure(text="Resume" if paused else "Pause")

        if rgb is not None:
            h, w, _ = rgb.shape
            scale = min(400 / w, 300 / h)
            nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
            img = Image.fromarray(rgb)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(nw, nh))
            self.video_lbl.configure(image=ctk_img)
            self.video_lbl._image_ref = ctk_img

        self.after(30, self._update_ui)

    def _on_close(self) -> None:
        with self.lock:
            self.running = False
            CONFIG_PATH.write_text(json.dumps(self.cfg, indent=2) + "\n", encoding="utf-8")
        if self.cap is not None:
            self.cap.release()
        self.listener.stop()
        self.landmarker.close()
        self.sock.close()
        self.destroy()


def main() -> None:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    app = GenesisHeadTrackerApp(cfg)
    app.mainloop()


if __name__ == "__main__":
    main()
