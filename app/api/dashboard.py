from __future__ import annotations
import psutil
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.config import settings
from app.core.auth import verify_login, is_logged_in
from app.models.camera import Camera
from app.models.worker import Worker
from app.models.alert import Alert
from app.vision.camera_manager import camera_manager

try:
    import torch
    CUDA_AVAILABLE = torch.cuda.is_available()
except Exception:
    CUDA_AVAILABLE = False

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    cameras = db.query(Camera).all()
    workers = db.query(Worker).all()
    open_alerts = db.query(Alert).filter(Alert.status == "OPEN").all()

    cams_online = 0
    working, idle = 0, 0
    per_camera = []
    for cam in cameras:
        w = camera_manager.get_worker(cam.camera_id)
        status = w.stream.status if w else "OFFLINE"
        is_sim = w.stream.is_simulated if w else False
        active_workers = w.latest_workers if w else []
        if status in ("ONLINE", "SIMULATED"):
            cams_online += 1
        cam_working = sum(1 for x in active_workers if x["activity"]["state"] == "WORKING")
        cam_idle = sum(1 for x in active_workers if x["activity"]["state"] == "IDLE")
        working += cam_working
        idle += cam_idle
        cam_alerts = [a for a in open_alerts if a.camera_id == cam.camera_id]
        per_camera.append({
            "camera_id": cam.camera_id,
            "name": cam.name,
            "location": cam.location,
            "status": status,
            "is_simulated": is_sim,
            "workers_detected": len(active_workers),
            "working": cam_working,
            "idle": cam_idle,
            "alerts": len(cam_alerts),
        })

    total_active_workers = sum(c["workers_detected"] for c in per_camera)
    compliance_pct = None
    if total_active_workers:
        compliance_pct = round(100 * working / total_active_workers, 1)

    return {
        "company": settings.company_name,
        "plant": settings.app_name,
        "system_status": "ONLINE",
        "demo_mode": settings.demo_mode,
        "cameras_total": len(cameras),
        "cameras_online": cams_online,
        "workers_registered": len(workers),
        "active_workers": total_active_workers,
        "working": working,
        "potential_idle": idle,
        "active_alerts": len(open_alerts),
        "process_compliance_pct": compliance_pct,
        "cameras": per_camera,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/performance")
def performance_snapshot():
    cpu = psutil.cpu_percent(interval=0.2)
    mem = psutil.virtual_memory()
    streams = camera_manager.status_snapshot()
    return {
        "cpu_percent": cpu,
        "ram_percent": mem.percent,
        "ram_used_gb": round(mem.used / (1024 ** 3), 2),
        "ram_total_gb": round(mem.total / (1024 ** 3), 2),
        "gpu": "CUDA available" if CUDA_AVAILABLE else "CPU MODE",
        "inference_fps_target": settings.inference_fps,
        "active_streams": len(streams),
        "streams": streams,
    }


class LoginPayload(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(payload: LoginPayload, request: Request):
    if verify_login(payload.username, payload.password):
        request.session["is_admin"] = True
        return {"success": True}
    raise HTTPException(401, "Invalid credentials")


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"success": True}


@router.get("/session")
def session_status(request: Request):
    return {"is_admin": is_logged_in(request)}
