from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.core.database import get_db
from app.models.worker import Worker
from app.models.event import ActivityEvent
from app.models.alert import Alert

router = APIRouter(prefix="/api/workers", tags=["workers"])


@router.get("")
def list_workers(db: Session = Depends(get_db)):
    return [w.to_dict() for w in db.query(Worker).all()]


@router.get("/{worker_id}")
def get_worker(worker_id: str, db: Session = Depends(get_db)):
    w = db.query(Worker).filter(Worker.worker_id == worker_id).first()
    if not w:
        raise HTTPException(404, "Worker not found")
    since = datetime.utcnow() - timedelta(hours=12)
    events = (
        db.query(ActivityEvent)
        .filter(ActivityEvent.worker_id == worker_id, ActivityEvent.timestamp >= since)
        .order_by(ActivityEvent.timestamp.desc())
        .limit(100)
        .all()
    )
    alerts = (
        db.query(Alert)
        .filter(Alert.worker_id == worker_id)
        .order_by(Alert.timestamp.desc())
        .limit(50)
        .all()
    )
    d = w.to_dict()
    d["recent_events"] = [e.to_dict() for e in events]
    d["recent_alerts"] = [a.to_dict() for a in alerts]
    return d
