from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.alert import Alert
from app.intelligence.alert_manager import alert_manager

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    db: Session = Depends(get_db),
    status: str | None = None,
    severity: str | None = None,
    camera_id: str | None = None,
    worker_id: str | None = None,
    limit: int = Query(100, le=500),
):
    q = db.query(Alert)
    if status:
        q = q.filter(Alert.status == status)
    if severity:
        q = q.filter(Alert.severity == severity)
    if camera_id:
        q = q.filter(Alert.camera_id == camera_id)
    if worker_id:
        q = q.filter(Alert.worker_id == worker_id)
    rows = q.order_by(Alert.timestamp.desc()).limit(limit).all()
    return [r.to_dict() for r in rows]


@router.get("/{alert_id}")
def get_alert(alert_id: str, db: Session = Depends(get_db)):
    a = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not a:
        raise HTTPException(404, "Alert not found")
    return a.to_dict()


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str):
    ok = alert_manager.acknowledge(alert_id)
    if not ok:
        raise HTTPException(404, "Alert not found")
    return {"alert_id": alert_id, "status": "ACKNOWLEDGED"}
