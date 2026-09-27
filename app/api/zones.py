from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import require_admin
from app.models.zone import Zone
from app.vision.zones import zone_manager

router = APIRouter(prefix="/api/zones", tags=["zones"])


class ZoneCreate(BaseModel):
    zone_id: str
    camera_id: str
    name: str
    zone_type: str = "WORKSTATION"
    x1: float
    y1: float
    x2: float
    y2: float


@router.get("")
def list_zones(db: Session = Depends(get_db), camera_id: str | None = None):
    q = db.query(Zone)
    if camera_id:
        q = q.filter(Zone.camera_id == camera_id)
    return [z.to_dict() for z in q.all()]


@router.post("", dependencies=[Depends(require_admin)])
def create_zone(payload: ZoneCreate, db: Session = Depends(get_db)):
    if db.query(Zone).filter(Zone.zone_id == payload.zone_id).first():
        raise HTTPException(400, "zone_id already exists")
    z = Zone(**payload.model_dump())
    db.add(z)
    db.commit()
    zone_manager.reload(db)
    return z.to_dict()


@router.delete("/{zone_id}", dependencies=[Depends(require_admin)])
def delete_zone(zone_id: str, db: Session = Depends(get_db)):
    z = db.query(Zone).filter(Zone.zone_id == zone_id).first()
    if not z:
        raise HTTPException(404, "Zone not found")
    db.delete(z)
    db.commit()
    zone_manager.reload(db)
    return {"deleted": zone_id}
