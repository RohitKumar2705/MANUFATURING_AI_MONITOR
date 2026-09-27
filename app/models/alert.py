from sqlalchemy import Column, String, Integer, DateTime, Float, Boolean
from datetime import datetime, timezone
from app.core.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=lambda: datetime.utcnow())
    camera_id = Column(String, nullable=True)
    worker_id = Column(String, nullable=True)
    type = Column(String, nullable=False)       # Potential Idle | Restricted Zone | PPE Violation | ...
    severity = Column(String, nullable=False)   # INFO|LOW|MEDIUM|HIGH|CRITICAL
    message = Column(String, nullable=False)
    confidence = Column(Float, nullable=True)         # null if not a model-confidence value
    basis = Column(String, default="rule_based")      # rule_based | model_inference | simulated
    status = Column(String, default="OPEN")           # OPEN|ACKNOWLEDGED
    snapshot = Column(String, nullable=True)          # path under data/alerts/
    simulated = Column(Boolean, default=False)

    def to_dict(self):
        return {
            "alert_id": self.alert_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "camera_id": self.camera_id,
            "worker_id": self.worker_id,
            "type": self.type,
            "severity": self.severity,
            "message": self.message,
            "confidence": self.confidence,
            "basis": self.basis,
            "status": self.status,
            "snapshot": self.snapshot,
            "simulated": self.simulated,
        }
