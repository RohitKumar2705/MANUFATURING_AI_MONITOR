"""
PPEDetector.

The spec is explicit: "Do NOT pretend PPE detection is working when the
model cannot actually detect it." No trained PPE-classification model ships
with this prototype (helmet/vest/gloves/mask/glasses/shoes classes are not
in stock COCO weights), so by default this class reports
MODEL_NOT_CONFIGURED for every PPE item rather than fabricating results.

If a real PPE model file is dropped at `models.ppe` in config.yaml, it is
loaded and used for genuine model_inference results instead.
"""
from __future__ import annotations
import threading
from pathlib import Path
from app.core.config import settings
from app.core.logging_setup import logger
from app.vision.interfaces import PPEModel

PPE_ITEMS = ["helmet", "vest", "gloves", "mask", "safety_glasses", "safety_shoes"]

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:  # pragma: no cover
    ULTRALYTICS_AVAILABLE = False


class PPEDetector(PPEModel):
    _instance: "PPEDetector | None" = None
    _lock = threading.Lock()

    def __init__(self):
        self.model = None
        self._loaded = False
        self._try_load()

    def _try_load(self):
        path = Path(settings.ppe_model_path)
        if not ULTRALYTICS_AVAILABLE or not path.exists():
            logger.info("PPE model not configured - PPE detection will report MODEL_NOT_CONFIGURED")
            return
        try:
            self.model = YOLO(str(path))
            self._loaded = True
            logger.info(f"PPE model loaded: {path}")
        except Exception as e:
            logger.warning(f"Failed to load PPE model at {path}: {e}")

    @classmethod
    def instance(cls) -> "PPEDetector":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def is_configured(self) -> bool:
        return self._loaded

    def predict(self, frame, person_bbox) -> dict:
        """Return {item: 'PRESENT'|'MISSING'|'UNKNOWN'|'MODEL_NOT_CONFIGURED'}"""
        if not self._loaded:
            return {item: "MODEL_NOT_CONFIGURED" for item in PPE_ITEMS}
        x1, y1, x2, y2 = [int(v) for v in person_bbox]
        crop = frame[max(0, y1):y2, max(0, x1):x2]
        if crop.size == 0:
            return {item: "UNKNOWN" for item in PPE_ITEMS}
        try:
            results = self.model.predict(crop, conf=settings.confidence, verbose=False)
        except Exception as e:
            logger.error(f"PPE inference error: {e}")
            return {item: "UNKNOWN" for item in PPE_ITEMS}
        detected = set()
        if results and results[0].boxes is not None:
            names = self.model.names
            for box in results[0].boxes:
                cls_id = int(box.cls[0])
                detected.add(names.get(cls_id, "").lower())
        return {item: ("PRESENT" if item in detected else "MISSING") for item in PPE_ITEMS}
