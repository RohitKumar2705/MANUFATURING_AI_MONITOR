"""
PoseEngine: lightweight pose estimation using YOLOv8-Pose.

Used by the ActivityEngine as one signal (limb movement) among several when
deciding WORKING vs IDLE vs WALKING. This is real model inference; if the
pose model fails to load, the ActivityEngine simply falls back to
bbox-motion-only inference and is transparent about that in the UI.
"""
from __future__ import annotations
import threading
from app.core.config import settings
from app.core.logging_setup import logger

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:  # pragma: no cover
    ULTRALYTICS_AVAILABLE = False


class PoseEngine:
    _instance: "PoseEngine | None" = None
    _lock = threading.Lock()

    def __init__(self):
        self.model = None
        self.model_loaded = False
        self._load()

    def _load(self):
        if not ULTRALYTICS_AVAILABLE:
            return
        try:
            self.model = YOLO(settings.pose_model_path)
            self.model_loaded = True
            logger.info(f"Pose model loaded: {settings.pose_model_path}")
        except Exception as e:
            logger.warning(f"Pose model not available ({e}); activity inference will use motion-only signals")
            self.model = None
            self.model_loaded = False

    @classmethod
    def instance(cls) -> "PoseEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def predict(self, frame) -> list[dict]:
        """Return list of {bbox, keypoints (17x3 array), confidence}."""
        if not self.model_loaded:
            return []
        try:
            results = self.model.predict(frame, conf=settings.confidence, verbose=False)
        except Exception as e:
            logger.error(f"Pose inference error: {e}")
            return []
        out = []
        if not results:
            return out
        r = results[0]
        if r.keypoints is None or r.boxes is None:
            return out
        kpts = r.keypoints.data.tolist()  # N x 17 x 3 (x, y, conf)
        for i, box in enumerate(r.boxes):
            out.append({
                "bbox": tuple(box.xyxy[0].tolist()),
                "confidence": float(box.conf[0]),
                "keypoints": kpts[i] if i < len(kpts) else [],
            })
        return out

    def keypoint_motion_score(self, kpts_a: list, kpts_b: list) -> float:
        """Average per-keypoint displacement between two pose readings (pixels)."""
        if not kpts_a or not kpts_b or len(kpts_a) != len(kpts_b):
            return 0.0
        total = 0.0
        n = 0
        for (xa, ya, ca), (xb, yb, cb) in zip(kpts_a, kpts_b):
            if ca > 0.3 and cb > 0.3:
                total += ((xa - xb) ** 2 + (ya - yb) ** 2) ** 0.5
                n += 1
        return total / n if n else 0.0
