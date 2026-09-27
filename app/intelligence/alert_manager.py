"""
AlertManager (spec sections 18, 19, 54).

Applies an alert cooldown per (camera_id, worker_id, alert_type) so a
persistent condition (e.g. idle for 5 minutes) raises ONE alert, not one
every frame. Also owns snapshot capture to data/alerts/.
"""
from __future__ import annotations
import os
import time
import uuid
import cv2
from datetime import datetime, timezone
from app.core.config import BASE_DIR, settings
from app.core.database import SessionLocal
from app.models.alert import Alert
from app.core.logging_setup import logger

SNAPSHOT_DIR = os.path.join(BASE_DIR, "data", "alerts")
os.makedirs(SNAPSHOT_DIR, exist_ok=True)


class AlertManager:
    def __init__(self):
        # key -> last_fired_timestamp
        self._last_fired: dict[tuple, float] = {}
        self._subscribers = []  # list[callable(alert_dict)]

    def subscribe(self, callback):
        self._subscribers.append(callback)

    def _notify(self, alert_dict: dict):
        for cb in self._subscribers:
            try:
                cb(alert_dict)
            except Exception as e:
                logger.error(f"Alert subscriber error: {e}")

    def _cooldown_key(self, camera_id, worker_id, alert_type):
        return (camera_id, worker_id, alert_type)

    def can_fire(self, camera_id, worker_id, alert_type, cooldown_seconds: float) -> bool:
        key = self._cooldown_key(camera_id, worker_id, alert_type)
        last = self._last_fired.get(key, 0)
        return (time.time() - last) >= cooldown_seconds

    def capture_snapshot(self, frame, camera_id: str) -> str | None:
        if frame is None:
            return None
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"alert_{ts}_{camera_id}.jpg"
        path = os.path.join(SNAPSHOT_DIR, filename)
        try:
            cv2.imwrite(path, frame)
            return f"data/alerts/{filename}"
        except Exception as e:
            logger.error(f"Snapshot capture failed: {e}")
            return None

    def raise_alert(
        self,
        camera_id: str | None,
        worker_id: str | None,
        alert_type: str,
        severity: str,
        message: str,
        confidence: float | None = None,
        basis: str = "rule_based",
        cooldown_seconds: float | None = None,
        frame=None,
        simulated: bool = False,
    ) -> dict | None:
        cooldown = cooldown_seconds if cooldown_seconds is not None else settings.alert_default_cooldown
        if not self.can_fire(camera_id, worker_id, alert_type, cooldown):
            return None

        key = self._cooldown_key(camera_id, worker_id, alert_type)
        self._last_fired[key] = time.time()

        snapshot_path = self.capture_snapshot(frame, camera_id) if frame is not None else None

        alert_id = f"ALERT-{uuid.uuid4().hex[:10].upper()}"
        db = SessionLocal()
        try:
            row = Alert(
                alert_id=alert_id,
                camera_id=camera_id,
                worker_id=worker_id,
                type=alert_type,
                severity=severity,
                message=message,
                confidence=confidence,
                basis=basis,
                status="OPEN",
                snapshot=snapshot_path,
                simulated=simulated,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            alert_dict = row.to_dict()
        except Exception as e:
            logger.error(f"Failed to persist alert: {e}")
            db.rollback()
            return None
        finally:
            db.close()

        logger.warning(f"ALERT [{severity}] {alert_type} - {message}")
        self._notify(alert_dict)
        return alert_dict

    def acknowledge(self, alert_id: str) -> bool:
        db = SessionLocal()
        try:
            row = db.query(Alert).filter(Alert.alert_id == alert_id).first()
            if not row:
                return False
            row.status = "ACKNOWLEDGED"
            db.commit()
            return True
        finally:
            db.close()


alert_manager = AlertManager()
