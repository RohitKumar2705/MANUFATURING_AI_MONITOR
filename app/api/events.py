from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.event import ActivityEvent, CameraEvent, SystemEvent

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
def list_events(
    db: Session = Depends(get_db),
    camera_id: str | None = None,
    worker_id: str | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(200, le=1000),
):
    q = db.query(ActivityEvent)
    if camera_id:
        q = q.filter(ActivityEvent.camera_id == camera_id)
    if worker_id:
        q = q.filter(ActivityEvent.worker_id == worker_id)
    if event_type:
        q = q.filter(ActivityEvent.event_type == event_type)
    if severity:
        q = q.filter(ActivityEvent.severity == severity)
    if date_from:
        q = q.filter(ActivityEvent.timestamp >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.filter(ActivityEvent.timestamp <= datetime.fromisoformat(date_to))
    rows = q.order_by(ActivityEvent.timestamp.desc()).limit(limit).all()
    return [r.to_dict() for r in rows]


@router.get("/camera")
def list_camera_events(db: Session = Depends(get_db), limit: int = 100):
    rows = db.query(CameraEvent).order_by(CameraEvent.timestamp.desc()).limit(limit).all()
    return [r.to_dict() for r in rows]


@router.get("/system")
def list_system_events(db: Session = Depends(get_db), limit: int = 100):
    rows = db.query(SystemEvent).order_by(SystemEvent.timestamp.desc()).limit(limit).all()
    return [r.to_dict() for r in rows]
