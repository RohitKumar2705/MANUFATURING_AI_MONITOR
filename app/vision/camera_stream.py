"""
CameraStream: a threaded wrapper around a single cv2.VideoCapture source
(webcam index, RTSP/HTTP URL, or video file). Runs its own read-loop in a
background thread so a slow/stalled camera never blocks the others
(spec section 56: multi-camera concurrency).

If the real source cannot be opened (spec section 35/60), and the camera is
flagged demo/simulated, falls back to a synthetic OpenCV-generated stream
that is always visibly labeled "SIMULATED CAMERA" so it is never confused
with a genuine feed.
"""
from __future__ import annotations

import cv2
import time
import threading
import numpy as np
from app.core.logging_setup import logger


class SyntheticCameraGenerator:
    """Generates a moving-'worker'-box synthetic video frame when no real
    camera/demo file is available. Always overlays SIMULATED CAMERA."""

    def __init__(self, camera_id: str, label: str, width=640, height=480):
        self.camera_id = camera_id
        self.label = label
        self.width = width
        self.height = height
        self.t0 = time.time()

    def next_frame(self) -> np.ndarray:
        t = time.time() - self.t0
        frame = np.full((self.height, self.width, 3), (32, 32, 36), dtype=np.uint8)

        # floor grid for an "industrial" look
        for gx in range(0, self.width, 40):
            cv2.line(frame, (gx, 0), (gx, self.height), (45, 45, 50), 1)
        for gy in range(0, self.height, 40):
            cv2.line(frame, (0, gy), (self.width, gy), (45, 45, 50), 1)

        # simple moving rectangle to simulate a "worker" silhouette walking around
        cx = int(self.width / 2 + (self.width / 3) * np.sin(t / 4.0))
        cy = int(self.height / 2 + (self.height / 4) * np.cos(t / 6.0))
        w, h = 60, 140
        top_left = (cx - w // 2, cy - h // 2)
        bottom_right = (cx + w // 2, cy + h // 2)
        cv2.rectangle(frame, top_left, bottom_right, (90, 160, 90), -1)
        cv2.circle(frame, (cx, cy - h // 2 - 15), 18, (90, 160, 90), -1)

        cv2.putText(frame, "SIMULATED CAMERA", (16, 30), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0, 210, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, self.label, (16, self.height - 16), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (200, 200, 200), 1, cv2.LINE_AA)
        return frame


class CameraStream:
    def __init__(self, camera_id: str, name: str, source, source_type: str,
                 fallback_to_synthetic: bool = True):
        self.camera_id = camera_id
        self.name = name
        self.source = source
        self.source_type = source_type
        self.fallback_to_synthetic = fallback_to_synthetic

        self._cap: cv2.VideoCapture | None = None
        self._synthetic: SyntheticCameraGenerator | None = None
        self.is_simulated = False
        self.status = "OFFLINE"

        self._latest_frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.frame_count = 0
        self.actual_fps = 0.0
        self._fps_window: list[float] = []

    # -- lifecycle -------------------------------------------------------
    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        if self._cap:
            self._cap.release()

    def _open_capture(self) -> bool:
        try:
            if self.source_type == "webcam":
                cap = cv2.VideoCapture(int(self.source))
            else:
                cap = cv2.VideoCapture(self.source)
            if cap is not None and cap.isOpened():
                self._cap = cap
                return True
        except Exception as e:
            logger.warning(f"[{self.camera_id}] failed to open source '{self.source}': {e}")
        return False

    def _run(self):
        opened = self._open_capture()
        if not opened:
            if self.fallback_to_synthetic:
                logger.info(f"[{self.camera_id}] real source unavailable -> using SIMULATED CAMERA")
                self._synthetic = SyntheticCameraGenerator(self.camera_id, self.name)
                self.is_simulated = True
                self.status = "SIMULATED"
            else:
                self.status = "ERROR"
                logger.error(f"[{self.camera_id}] source unavailable and no fallback configured")
                return
        else:
            self.status = "ONLINE"

        last_tick = time.time()
        while not self._stop_event.is_set():
            frame = None
            if self._synthetic is not None:
                frame = self._synthetic.next_frame()
                time.sleep(1 / 15.0)
            else:
                ok, frame = self._cap.read()
                if not ok or frame is None:
                    if self.source_type == "video_file":
                        # loop the demo video
                        self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ok, frame = self._cap.read()
                        if not ok:
                            frame = None
                    if frame is None:
                        self.status = "ERROR"
                        logger.warning(f"[{self.camera_id}] read failed - attempting reconnect")
                        time.sleep(1.0)
                        if self.fallback_to_synthetic and self._synthetic is None and self.source_type != "video_file":
                            reopened = self._open_capture()
                            if not reopened:
                                self._synthetic = SyntheticCameraGenerator(self.camera_id, self.name)
                                self.is_simulated = True
                                self.status = "SIMULATED"
                        continue
                self.status = "ONLINE" if not self.is_simulated else "SIMULATED"

            with self._lock:
                self._latest_frame = frame
            self.frame_count += 1

            now = time.time()
            self._fps_window.append(now)
            self._fps_window = [t for t in self._fps_window if now - t <= 2.0]
            self.actual_fps = len(self._fps_window) / 2.0

    def read(self) -> np.ndarray | None:
        with self._lock:
            return None if self._latest_frame is None else self._latest_frame.copy()
