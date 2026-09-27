from __future__ import annotations
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings, BASE_DIR
from app.core.logging_setup import logger
from app.core.database import init_db, SessionLocal
from app.core.seed import seed_all
from app.models.camera import Camera
from app.vision.camera_manager import camera_manager
from app.services.ws_manager import connection_manager
from app.intelligence.alert_manager import alert_manager
from app.services.event_service import event_logger

from app.api import cameras, workers, alerts, events, processes, zones, dashboard, demo, pages

app = FastAPI(title="NovaTech AI Manufacturing Monitor")

app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
app.mount("/data", StaticFiles(directory=str(BASE_DIR / "data")), name="data")

app.include_router(pages.router)
app.include_router(cameras.router)
app.include_router(workers.router)
app.include_router(alerts.router)
app.include_router(events.router)
app.include_router(processes.router)
app.include_router(zones.router)
app.include_router(dashboard.router)
app.include_router(demo.router)


def _on_camera_update(camera_id: str, payload: dict):
    """Called from a camera worker thread - forward to all WS clients."""
    connection_manager.broadcast({"type": "worker_update", **payload})


def _on_alert(alert_dict: dict):
    connection_manager.broadcast({"type": "alert", "alert": alert_dict})


@app.on_event("startup")
async def startup():
    logger.info("=" * 70)
    logger.info(f"Starting {settings.company_name} - {settings.app_name}")
    logger.info("=" * 70)

    init_db()
    seed_all()

    from app.intelligence.rule_engine import rule_engine as _rule_engine
    _rule_engine.reload()

    connection_manager.bind_loop(asyncio.get_event_loop())
    alert_manager.subscribe(_on_alert)
    camera_manager.set_update_callback(_on_camera_update)

    db = SessionLocal()
    try:
        cams = db.query(Camera).filter(Camera.enabled == True).all()  # noqa: E712
        camera_manager.start_all(cams)
        for c in cams:
            event_logger.log_camera_event(c.camera_id, "CONNECTED", f"Camera worker started for {c.name}")
    finally:
        db.close()

    event_logger.log_system_event("STARTUP", "Application started successfully")
    logger.info(f"Dashboard ready at http://{settings.get('app.host','0.0.0.0')}:{settings.get('app.port',8000)}")


@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down - stopping all camera workers")
    camera_manager.stop_all()
    event_logger.log_system_event("SHUTDOWN", "Application shut down")


@app.websocket("/ws/dashboard")
async def ws_dashboard(ws: WebSocket):
    await connection_manager.connect(ws)
    try:
        while True:
            # Dashboard is a broadcast-only channel for now; just keep the
            # connection alive and drain any client pings.
            await ws.receive_text()
    except WebSocketDisconnect:
        connection_manager.disconnect(ws)
    except Exception:
        connection_manager.disconnect(ws)
