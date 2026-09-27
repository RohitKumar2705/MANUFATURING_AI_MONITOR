from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import require_admin
from app.models.process import Process, ProcessState
from app.intelligence.rule_engine import rule_engine

router = APIRouter(prefix="/api/processes", tags=["processes"])


class ProcessCreate(BaseModel):
    process_id: str
    name: str
    workstation: str
    camera_id: str | None = None
    steps: list[str]


@router.get("")
def list_processes(db: Session = Depends(get_db)):
    return [p.to_dict() for p in db.query(Process).all()]


@router.get("/states")
def list_process_states(db: Session = Depends(get_db)):
    """Latest process state per (worker, process) pair - used by the Process Monitoring page."""
    rows = db.query(ProcessState).order_by(ProcessState.id.desc()).all()
    seen = set()
    out = []
    for r in rows:
        key = (r.worker_id, r.process_id)
        if key in seen:
            continue
        seen.add(key)
        d = r.to_dict()
        proc = db.query(Process).filter(Process.process_id == r.process_id).first()
        if proc:
            d["process_name"] = proc.name
            d["total_steps"] = len(proc.steps)
            d["steps"] = proc.steps
        out.append(d)
    return out


@router.post("", dependencies=[Depends(require_admin)])
def create_process(payload: ProcessCreate, db: Session = Depends(get_db)):
    if db.query(Process).filter(Process.process_id == payload.process_id).first():
        raise HTTPException(400, "process_id already exists")
    p = Process(**payload.model_dump())
    db.add(p)
    db.commit()
    return p.to_dict()
