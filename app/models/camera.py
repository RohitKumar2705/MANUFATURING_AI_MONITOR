from sqlalchemy import Column, String, Integer, Boolean, Float, DateTime
from datetime import datetime, timezone
from app.core.database import Base


class Camera(Base):
    __tablename__ = "cameras"

    camera_id = Column(String, primary_key=True)      # e.g. "CAM-001"
    name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    purpose = Column(String, default="")
    source = Column(String, nullable=False)            # "0", url, or file path
    type = Column(String, nullable=False)               # webcam|mobile_ip_camera|rtsp|video_file|image_sequence
    status = Column(String, default="OFFLINE")          # ONLINE|OFFLINE|ERROR|SIMULATED
    fps = Column(Float, default=30.0)
    resolution = Column(String, default="640x480")
    enabled = Column(Boolean, default=True)
    is_simulated = Column(Boolean, default=False)
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    def to_dict(self):
        return {
            "camera_id": self.camera_id,
            "name": self.name,
            "location": self.location,
            "purpose": self.purpose,
            "source": self.source,
            "type": self.type,
            "status": self.status,
            "fps": self.fps,
            "resolution": self.resolution,
            "enabled": self.enabled,
            "is_simulated": self.is_simulated,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }
