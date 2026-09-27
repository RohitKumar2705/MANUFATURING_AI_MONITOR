"""
ZoneManager: determines which configured zone a detected worker's bbox
center falls inside, for a given camera. Zone coordinates are stored
normalized (0..1) so they stay resolution-independent (spec section 28).
"""
from __future__ import annotations
from sqlalchemy.orm import Session
from app.models.zone import Zone


class ZoneManager:
    def __init__(self):
        # camera_id -> list[Zone] cache, refreshed via reload()
        self._cache: dict[str, list[Zone]] = {}

    def reload(self, db: Session):
        zones = db.query(Zone).all()
        cache: dict[str, list[Zone]] = {}
        for z in zones:
            cache.setdefault(z.camera_id, []).append(z)
        self._cache = cache

    def zones_for_camera(self, camera_id: str) -> list[Zone]:
        return self._cache.get(camera_id, [])

    def locate(self, camera_id: str, bbox: tuple[float, float, float, float],
               frame_w: int, frame_h: int) -> Zone | None:
        """Return the Zone containing the bbox's bottom-center point (feet position),
        which is a better proxy for "which zone is this person standing in" than
        the bbox centroid."""
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2.0
        cy = y2  # bottom of the box ~ where the person is standing
        nx, ny = cx / frame_w, cy / frame_h
        for z in self._cache.get(camera_id, []):
            if z.contains_point(nx, ny):
                return z
        return None


zone_manager = ZoneManager()
