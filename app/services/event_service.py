"""EventLogger: writes rows to activity_events / camera_events / system_events."""
from __future__ import annotations
from app.core.database import SessionLocal
from app.models.event import ActivityEvent, CameraEvent, SystemEvent
from app.core.logging_setup import logger


class EventLogger:
    def log_activity(self, camera_id: str | None, worker_id: str | None,
                      event_type: str, description: str, severity: str = "INFO"):
        db = SessionLocal()
        try:
            ev = ActivityEvent(
                camera_id=camera_id, worker_id=worker_id,
                event_type=event_type, description=description, severity=severity,
            )
            db.add(ev)
            db.commit()
        except Exception as e:
            logger.error(f"EventLogger.log_activity failed: {e}")
            db.rollback()
        finally:
            db.close()

    def log_camera_event(self, camera_id: str, event_type: str, message: str = ""):
        db = SessionLocal()
        try:
            ev = CameraEvent(camera_id=camera_id, event_type=event_type, message=message)
            db.add(ev)
            db.commit()
        except Exception as e:
            logger.error(f"EventLogger.log_camera_event failed: {e}")
            db.rollback()
        finally:
            db.close()

    def log_system_event(self, event_type: str, message: str = ""):
        db = SessionLocal()
        try:
            ev = SystemEvent(event_type=event_type, message=message)
            db.add(ev)
            db.commit()
        except Exception as e:
            logger.error(f"EventLogger.log_system_event failed: {e}")
            db.rollback()
        finally:
            db.close()


event_logger = EventLogger()
