from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON
from datetime import datetime, timezone
from app.core.database import Base


class Process(Base):
    __tablename__ = "processes"

    process_id = Column(String, primary_key=True)   # e.g. "ASSEMBLY_A"
    name = Column(String, nullable=False)
    workstation = Column(String, nullable=False)     # zone name / workstation this process applies to
    camera_id = Column(String, ForeignKey("cameras.camera_id"), nullable=True)
    steps = Column(JSON, nullable=False)             # ordered list[str] of step ids

    def to_dict(self):
        return {
            "process_id": self.process_id,
            "name": self.name,
            "workstation": self.workstation,
            "camera_id": self.camera_id,
            "steps": self.steps,
        }


class ProcessState(Base):
    """Live runtime state of a process instance for a given worker/workstation."""
    __tablename__ = "process_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    process_id = Column(String, ForeignKey("processes.process_id"), nullable=False)
    worker_id = Column(String, ForeignKey("workers.worker_id"), nullable=True)
    camera_id = Column(String, nullable=False)
    current_step_index = Column(Integer, default=0)
    completed_steps = Column(JSON, default=list)
    skipped_steps = Column(JSON, default=list)
    process_status = Column(String, default="NOT_STARTED")  # NOT_STARTED|IN_PROGRESS|COMPLETED|DEVIATION|UNKNOWN
    process_started_at = Column(DateTime, nullable=True)
    last_activity = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "process_id": self.process_id,
            "worker_id": self.worker_id,
            "camera_id": self.camera_id,
            "current_step_index": self.current_step_index,
            "completed_steps": self.completed_steps,
            "skipped_steps": self.skipped_steps,
            "process_status": self.process_status,
            "process_started_at": self.process_started_at.isoformat() if self.process_started_at else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
        }
