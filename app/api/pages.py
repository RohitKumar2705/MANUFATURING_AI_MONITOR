from __future__ import annotations
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings, BASE_DIR
from app.core.auth import is_logged_in
from app.models.camera import Camera

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


def _ctx(request: Request, **kwargs):
    base = {
        "company_name": settings.company_name,
        "plant_name": settings.app_name,
        "demo_mode": settings.demo_mode,
        "is_admin": is_logged_in(request),
    }
    base.update(kwargs)
    return base


def render(request: Request, name: str, **kwargs):
    return templates.TemplateResponse(request, name, _ctx(request, **kwargs))


@router.get("/")
def dashboard_page(request: Request, db: Session = Depends(get_db)):
    cameras = db.query(Camera).order_by(Camera.camera_id).all()
    return render(request, "dashboard.html", cameras=cameras)


@router.get("/camera/{camera_id}")
def camera_detail_page(camera_id: str, request: Request, db: Session = Depends(get_db)):
    cam = db.query(Camera).filter(Camera.camera_id == camera_id).first()
    return render(request, "camera_detail.html", camera=cam, camera_id=camera_id)


@router.get("/workers")
def workers_page(request: Request):
    return render(request, "workers.html")


@router.get("/worker/{worker_id}")
def worker_detail_page(worker_id: str, request: Request):
    return render(request, "worker_detail.html", worker_id=worker_id)


@router.get("/alerts")
def alerts_page(request: Request):
    return render(request, "alerts.html")


@router.get("/events")
def events_page(request: Request):
    return render(request, "events.html")


@router.get("/analytics")
def analytics_page(request: Request):
    return render(request, "analytics.html")


@router.get("/process-monitoring")
def process_monitoring_page(request: Request):
    return render(request, "process_monitoring.html")


@router.get("/settings")
def settings_page(request: Request, db: Session = Depends(get_db)):
    cameras = db.query(Camera).order_by(Camera.camera_id).all()
    return render(request, "settings.html", cameras=cameras)


@router.get("/login")
def login_page(request: Request):
    return render(request, "login.html")
