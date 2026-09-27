"""
DetectionEngine: wraps an Ultralytics YOLO model for object/person detection.

This is real AI inference (not simulated) whenever `model_loaded` is True.
"""
from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Optional

from app.core.config import settings
from app.core.logging_setup import logger
from app.vision.interfaces import DetectionModel

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:  # pragma: no cover
    ULTRALYTICS_AVAILABLE = False


@dataclass
class DetectionResult:
    class_id: int
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]   # x1, y1, x2, y2 (pixels)
    timestamp: float
    camera_id: str
    track_id: Optional[int] = None


class DetectionEngine(DetectionModel):
    """
    Loads a YOLO model once and reuses it for every camera. Ultralytics'
    `.track()` API is used elsewhere (TrackingEngine) so this class also
    exposes a `track_frame` helper alongside plain `predict`.
    """

    _instance: "DetectionEngine | None" = None
    _lock = threading.Lock()

    def __init__(self):
        self.model = None
        self.model_loaded = False
        self.class_names: dict[int, str] = {}
        self._load()

    def _load(self):
        if not ULTRALYTICS_AVAILABLE:
            logger.error("Ultralytics not installed - detection disabled (MODEL NOT CONFIGURED)")
            return
        try:
            self.model = YOLO(settings.detection_model_path)
            self.class_names = self.model.names
            self.model_loaded = True
            logger.info(f"Detection model loaded: {settings.detection_model_path}")
        except Exception as e:
            logger.error(f"Failed to load detection model: {e}")
            self.model = None
            self.model_loaded = False

    @classmethod
    def instance(cls) -> "DetectionEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def predict(self, frame) -> list[dict]:
        """Plain (untracked) detection - used for one-off tests."""
        if not self.model_loaded:
            return []
        results = self.model.predict(
            frame, conf=settings.confidence, iou=settings.iou, verbose=False,
        )
        return self._parse_results(results)

    def track_frame(self, frame, camera_id: str, persist: bool = True) -> list[DetectionResult]:
        """
        DEPRECATED for multi-camera use: Ultralytics' built-in persist=True
        tracker state lives on the shared model/predictor object, so calling
        this from several camera threads concurrently would let track IDs
        and state bleed between unrelated camera feeds. Use `predict_frame`
        (stateless) + a per-camera `TrackingEngine` instance instead - see
        app/vision/tracking.py. Kept only for quick single-camera testing.
        """
        if not self.model_loaded:
            return []
        try:
            results = self.model.track(
                frame,
                conf=settings.confidence,
                iou=settings.iou,
                tracker=settings.tracker_cfg,
                persist=persist,
                verbose=False,
            )
        except Exception as e:
            logger.error(f"[{camera_id}] tracking inference error: {e}")
            return []

        out: list[DetectionResult] = []
        now = time.time()
        if not results:
            return out
        r = results[0]
        if r.boxes is None:
            return out
        for box in r.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()
            track_id = int(box.id[0]) if box.id is not None else None
            out.append(DetectionResult(
                class_id=cls_id,
                class_name=self.class_names.get(cls_id, str(cls_id)),
                confidence=conf,
                bbox=tuple(xyxy),
                timestamp=now,
                camera_id=camera_id,
                track_id=track_id,
            ))
        return out

    def predict_frame(self, frame, camera_id: str) -> list[DetectionResult]:
        """Stateless per-frame detection (no tracking) - safe to call
        concurrently from multiple camera threads since Ultralytics'
        `.predict()` doesn't mutate shared tracker state. Track IDs are
        assigned afterwards by a per-camera `TrackingEngine`."""
        if not self.model_loaded:
            return []
        try:
            results = self.model.predict(frame, conf=settings.confidence, iou=settings.iou, verbose=False)
        except Exception as e:
            logger.error(f"[{camera_id}] detection inference error: {e}")
            return []
        out: list[DetectionResult] = []
        now = time.time()
        if not results:
            return out
        r = results[0]
        if r.boxes is None:
            return out
        for box in r.boxes:
            cls_id = int(box.cls[0])
            out.append(DetectionResult(
                class_id=cls_id,
                class_name=self.class_names.get(cls_id, str(cls_id)),
                confidence=float(box.conf[0]),
                bbox=tuple(box.xyxy[0].tolist()),
                timestamp=now,
                camera_id=camera_id,
                track_id=None,
            ))
        return out

    def _parse_results(self, results) -> list[dict]:
        out = []
        if not results:
            return out
        r = results[0]
        if r.boxes is None:
            return out
        for box in r.boxes:
            cls_id = int(box.cls[0])
            out.append({
                "class_id": cls_id,
                "class_name": self.class_names.get(cls_id, str(cls_id)),
                "confidence": float(box.conf[0]),
                "bbox": tuple(box.xyxy[0].tolist()),
            })
        return out
