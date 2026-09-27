from sqlalchemy import Column, String, Integer, DateTime, Float
from datetime import datetime, timezone
from app.core.database import Base


class ActivityEvent(Base):
    """General event log: zone entry, activity state change, process step, etc."""
    __tablename__ = "activity_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.utcnow())
    camera_id = Column(String, nullable=True)
    worker_id = Column(String, nullable=True)
    event_type = Column(String, nullable=False)   # ZONE_ENTER|ZONE_EXIT|ACTIVITY_CHANGE|PROCESS_STEP|PROCESS_COMPLETE|...
    description = Column(String, nullable=False)
    severity = Column(String, default="INFO")

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "camera_id": self.camera_id,
            "worker_id": self.worker_id,
            "event_type": self.event_type,
            "description": self.description,
            "severity": self.severity,
        }


class CameraEvent(Base):
    __tablename__ = "camera_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.utcnow())
    camera_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)   # CONNECTED|DISCONNECTED|ERROR|RECONNECTED
    message = Column(String, default="")

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "camera_id": self.camera_id,
            "event_type": self.event_type,
            "message": self.message,
        }


class SystemEvent(Base):
    __tablename__ = "system_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.utcnow())
    event_type = Column(String, nullable=False)
    message = Column(String, default="")

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "event_type": self.event_type,
            "message": self.message,
        }


class Detection(Base):
    """Raw per-frame detection log (kept lightweight - sampled, not every single frame)."""
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.utcnow())
    camera_id = Column(String, nullable=False)
    track_id = Column(Integer, nullable=True)
    class_name = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    bbox_x1 = Column(Float)
    bbox_y1 = Column(Float)
    bbox_x2 = Column(Float)
    bbox_y2 = Column(Float)
