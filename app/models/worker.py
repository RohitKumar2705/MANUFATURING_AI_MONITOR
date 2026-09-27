from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from datetime import datetime, timezone
from app.core.database import Base


class Worker(Base):
    __tablename__ = "workers"

    worker_id = Column(String, primary_key=True)   # e.g. "EMP-001"
    employee_code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    department = Column(String, default="")
    shift = Column(String, default="Day (09:00-18:00)")
    assigned_workstation = Column(String, default="")
    status = Column(String, default="OFFLINE")       # WORKING|POTENTIAL_IDLE|WALKING|UNKNOWN|OFFLINE
    current_camera = Column(String, nullable=True)
    current_zone = Column(String, nullable=True)
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    def to_dict(self):
        return {
            "worker_id": self.worker_id,
            "employee_code": self.employee_code,
            "name": self.name,
            "department": self.department,
            "shift": self.shift,
            "assigned_workstation": self.assigned_workstation,
            "status": self.status,
            "current_camera": self.current_camera,
            "current_zone": self.current_zone,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


class WorkerSession(Base):
    """A contiguous span during which a tracked person was linked to a worker id on a camera."""
    __tablename__ = "worker_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    worker_id = Column(String, ForeignKey("workers.worker_id"), nullable=True)
    camera_id = Column(String, ForeignKey("cameras.camera_id"), nullable=False)
    track_id = Column(Integer, nullable=False)
    started_at = Column(DateTime, default=lambda: datetime.utcnow())
    ended_at = Column(DateTime, nullable=True)
