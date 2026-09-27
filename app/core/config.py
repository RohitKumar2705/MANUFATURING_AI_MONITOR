"""
Central configuration loader.

Reads config.yaml once at import time and exposes a singleton `settings`
object. Every tunable threshold mentioned in the spec (idle thresholds,
inference FPS, confidence, cooldowns, etc.) lives in config.yaml so nothing
important is hard-coded in the vision/intelligence modules.
"""
from __future__ import annotations

import os
import yaml
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings:
    def __init__(self, path: str | Path = BASE_DIR / "config.yaml"):
        self._path = Path(path)
        self._raw: dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        if self._path.exists():
            with open(self._path, "r") as f:
                self._raw = yaml.safe_load(f) or {}
        else:
            self._raw = {}

    # -- generic dotted-path getter -----------------------------------
    def get(self, dotted_key: str, default: Any = None) -> Any:
        node: Any = self._raw
        for part in dotted_key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    # -- convenience properties ----------------------------------------
    @property
    def app_name(self) -> str:
        return self.get("app.name", "NovaTech Precision Components Plant")

    @property
    def company_name(self) -> str:
        return self.get("app.company", "NovaTech Manufacturing Pvt. Ltd.")

    @property
    def demo_mode(self) -> bool:
        env = os.environ.get("DEMO_MODE")
        if env is not None:
            return env.lower() in ("1", "true", "yes")
        return bool(self.get("app.demo_mode", True))

    @property
    def detection_model_path(self) -> str:
        return str(BASE_DIR / self.get("models.detection", "models/yolov8n.pt"))

    @property
    def pose_model_path(self) -> str:
        return str(BASE_DIR / self.get("models.pose", "models/yolov8n-pose.pt"))

    @property
    def ppe_model_path(self) -> str:
        return str(BASE_DIR / self.get("models.ppe", "models/ppe_model.pt"))

    @property
    def confidence(self) -> float:
        return float(self.get("inference.confidence", 0.45))

    @property
    def iou(self) -> float:
        return float(self.get("inference.iou", 0.5))

    @property
    def inference_fps(self) -> float:
        return float(self.get("inference.inference_fps", 8))

    @property
    def device(self) -> str:
        return str(self.get("inference.device", "cpu"))

    @property
    def tracker_cfg(self) -> str:
        return str(self.get("tracking.tracker", "bytetrack.yaml"))

    @property
    def idle_threshold(self) -> float:
        return float(self.get("activity.idle_threshold_seconds", 30))

    @property
    def critical_idle_threshold(self) -> float:
        return float(self.get("activity.critical_idle_threshold_seconds", 120))

    @property
    def walking_speed_threshold(self) -> float:
        return float(self.get("activity.walking_pixel_speed_threshold", 18))

    @property
    def working_motion_threshold(self) -> float:
        return float(self.get("activity.working_motion_threshold", 4))

    @property
    def min_history_seconds(self) -> float:
        return float(self.get("activity.min_history_seconds", 2))

    @property
    def alert_default_cooldown(self) -> float:
        return float(self.get("alerts.default_cooldown_seconds", 45))

    @property
    def idle_warning_cooldown(self) -> float:
        return float(self.get("alerts.idle_warning_cooldown_seconds", 60))

    @property
    def idle_critical_cooldown(self) -> float:
        return float(self.get("alerts.idle_critical_cooldown_seconds", 90))

    @property
    def restricted_zone_cooldown(self) -> float:
        return float(self.get("zones.restricted_alert_cooldown_seconds", 60))

    @property
    def process_step_stall_seconds(self) -> float:
        return float(self.get("process.step_stall_seconds", 90))

    @property
    def camera_reconnect_interval(self) -> float:
        return float(self.get("camera.reconnect_interval_seconds", 10))

    @property
    def admin_username(self) -> str:
        return os.environ.get(
            "ADMIN_USERNAME",
            str(self.get("security.admin_username", "admin")),
        )

    @property
    def admin_password(self) -> str:
        return os.environ.get("ADMIN_PASSWORD", "novatech123")

    @property
    def session_secret(self) -> str:
        return os.environ.get(
            "SESSION_SECRET",
            str(self.get("security.session_secret", "dev-secret")),
        )

    @property
    def log_level(self) -> str:
        return str(self.get("logging.level", "INFO"))

    @property
    def log_file(self) -> str:
        return str(BASE_DIR / self.get("logging.file", "logs/app.log"))


settings = Settings()
