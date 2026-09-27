from __future__ import annotations
import cv2
import time
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import require_admin
from app.models.camera import Camera
from app.vision.camera_manager import camera_manager
from app.services.event_service import event_logger

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


class CameraCreate(BaseModel):
    camera_id: str
    name: str
    location: str
    purpose: str = ""
    source: str
    type: str = "webcam"
    fps: float = 30.0
    resolution: str = "640x480"
    enabled: bool = True


class CameraUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    purpose: str | None = None
    source: str | None = None
    type: str | None = None
    fps: float | None = None
    resolution: str | None = None
    enabled: bool | None = None


@router.get("")
def list_cameras(db: Session = Depends(get_db)):
    cams = db.query(Camera).all()
    out = []
    for c in cams:
        d = c.to_dict()
        w = camera_manager.get_worker(c.camera_id)
        if w:
            d["status"] = w.stream.status
            d["is_simulated"] = w.stream.is_simulated
            d["actual_fps"] = round(w.stream.actual_fps, 1)
            d["active_workers"] = len(w.latest_workers)
        out.append(d)
    return out


@router.get("/{camera_id}")
def get_camera(camera_id: str, db: Session = Depends(get_db)):
    cam = db.query(Camera).filter(Camera.camera_id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")
    d = cam.to_dict()
    w = camera_manager.get_worker(camera_id)
    if w:
        d["status"] = w.stream.status
        d["is_simulated"] = w.stream.is_simulated
        d["actual_fps"] = round(w.stream.actual_fps, 1)
        d["workers"] = w.latest_workers
    return d


@router.post("", dependencies=[Depends(require_admin)])
def create_camera(payload: CameraCreate, db: Session = Depends(get_db)):
    if db.query(Camera).filter(Camera.camera_id == payload.camera_id).first():
        raise HTTPException(400, "camera_id already exists")
    cam = Camera(**payload.model_dump(), status="OFFLINE")
    db.add(cam)
    db.commit()
    db.refresh(cam)
    if cam.enabled:
        camera_manager.start_camera(cam)
    event_logger.log_system_event("CAMERA_CREATED", f"Camera {cam.camera_id} created")
    return cam.to_dict()


@router.put("/{camera_id}", dependencies=[Depends(require_admin)])
def update_camera(camera_id: str, payload: CameraUpdate, db: Session = Depends(get_db)):
    cam = db.query(Camera).filter(Camera.camera_id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cam, k, v)
    db.commit()
    db.refresh(cam)
    camera_manager.stop_camera(camera_id)
    if cam.enabled:
        camera_manager.start_camera(cam)
    return cam.to_dict()


@router.delete("/{camera_id}", dependencies=[Depends(require_admin)])
def delete_camera(camera_id: str, db: Session = Depends(get_db)):
    cam = db.query(Camera).filter(Camera.camera_id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")
    camera_manager.stop_camera(camera_id)
    db.delete(cam)
    db.commit()
    return {"deleted": camera_id}


@router.post("/test-connection")
def test_connection(source: str, type: str = "mobile_ip_camera"):
    """Spec section 6: 'Test Camera' button for mobile IP camera URLs."""
    try:
        src = int(source) if type == "webcam" else source
        cap = cv2.VideoCapture(src)
        ok = cap.isOpened()
        if ok:
            ret, _ = cap.read()
            ok = ok and ret
        cap.release()
        return {"result": "CONNECTED" if ok else "CONNECTION FAILED"}
    except Exception:
        return {"result": "CONNECTION FAILED"}


def _mjpeg_generator(camera_id: str):
    while True:
        worker = camera_manager.get_worker(camera_id)
        if worker is None:
            time.sleep(0.5)
            continue
        jpeg = worker.get_jpeg()
        if jpeg is not None:
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
        time.sleep(1 / 12.0)


@router.get("/{camera_id}/stream")
def video_stream(camera_id: str):
    return StreamingResponse(
        _mjpeg_generator(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
