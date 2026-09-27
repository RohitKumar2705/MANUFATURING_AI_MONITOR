from sqlalchemy import Column, String, Integer, Float, ForeignKey
from app.core.database import Base


class Zone(Base):
    __tablename__ = "zones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    zone_id = Column(String, unique=True, nullable=False)
    camera_id = Column(String, ForeignKey("cameras.camera_id"), nullable=False)
    name = Column(String, nullable=False)
    zone_type = Column(String, default="WORKSTATION")  # WORKSTATION|RESTRICTED|MATERIAL|SAFETY|INSPECTION|PACKAGING|OTHER
    # normalized rectangle coords (0..1) so they are resolution independent
    x1 = Column(Float, nullable=False)
    y1 = Column(Float, nullable=False)
    x2 = Column(Float, nullable=False)
    y2 = Column(Float, nullable=False)

    def to_dict(self):
        return {
            "zone_id": self.zone_id,
            "camera_id": self.camera_id,
            "name": self.name,
            "zone_type": self.zone_type,
            "x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2,
        }

    def contains_point(self, nx: float, ny: float) -> bool:
        return self.x1 <= nx <= self.x2 and self.y1 <= ny <= self.y2
