"""
Demo Control Panel (spec sections 59-60).

Lets a presenter trigger scenarios without a real factory. Every alert
raised from here is explicitly marked `simulated=True` and the message is
prefixed "[SIMULATED EVENT]" so it is never confused with a genuine
detection-driven alert (spec section 61 - never fake AI).
"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from app.core.auth import require_admin
from app.intelligence.alert_manager import alert_manager
from app.vision.camera_manager import camera_manager
from app.services.event_service import event_logger

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/simulate/idle")
def simulate_idle(camera_id: str = "CAM-001", worker_id: str = "EMP-001"):
    a = alert_manager.raise_alert(
        camera_id=camera_id, worker_id=worker_id, alert_type="Potential Idle",
        severity="MEDIUM",
        message=f"[SIMULATED EVENT] Potential idle activity manually simulated for {worker_id}",
        basis="simulated", cooldown_seconds=0, simulated=True,
    )
    event_logger.log_activity(camera_id, worker_id, "ACTIVITY_CHANGE",
                               "[SIMULATED EVENT] Activity changed: WORKING -> IDLE", severity="MEDIUM")
    return {"triggered": "idle", "alert": a}


@router.post("/simulate/ppe")
def simulate_ppe(camera_id: str = "CAM-001", worker_id: str = "EMP-001"):
    a = alert_manager.raise_alert(
        camera_id=camera_id, worker_id=worker_id, alert_type="PPE Violation",
        severity="HIGH",
        message=f"[SIMULATED EVENT] PPE violation manually simulated for {worker_id} (helmet missing)",
        basis="simulated", cooldown_seconds=0, simulated=True,
    )
    return {"triggered": "ppe_violation", "alert": a}


@router.post("/simulate/restricted-zone")
def simulate_restricted_zone(camera_id: str = "CAM-001", worker_id: str = "EMP-002"):
    a = alert_manager.raise_alert(
        camera_id=camera_id, worker_id=worker_id, alert_type="Restricted Zone",
        severity="CRITICAL",
        message=f"[SIMULATED EVENT] Restricted zone entry manually simulated for {worker_id}",
        basis="simulated", cooldown_seconds=0, simulated=True,
    )
    return {"triggered": "restricted_zone", "alert": a}


@router.post("/simulate/process-deviation")
def simulate_process_deviation(camera_id: str = "CAM-002", worker_id: str = "EMP-002"):
    a = alert_manager.raise_alert(
        camera_id=camera_id, worker_id=worker_id, alert_type="Process Deviation",
        severity="MEDIUM",
        message=f"[SIMULATED EVENT] Process deviation manually simulated for {worker_id} "
                f"(expected step 'fasten_component', observed 'inspect_component')",
        basis="simulated", cooldown_seconds=0, simulated=True,
    )
    return {"triggered": "process_deviation", "alert": a}


@router.post("/simulate/camera-offline")
def simulate_camera_offline(camera_id: str = "CAM-003"):
    w = camera_manager.get_worker(camera_id)
    if w:
        w.stream.status = "ERROR"
    a = alert_manager.raise_alert(
        camera_id=camera_id, worker_id=None, alert_type="Camera Offline",
        severity="HIGH",
        message=f"[SIMULATED EVENT] Camera {camera_id} manually disconnected for demo purposes",
        basis="simulated", cooldown_seconds=0, simulated=True,
    )
    event_logger.log_camera_event(camera_id, "DISCONNECTED", "[SIMULATED EVENT] manual demo disconnect")
    return {"triggered": "camera_offline", "alert": a}


@router.post("/reset")
def reset_demo(camera_id: str = "CAM-003"):
    w = camera_manager.get_worker(camera_id)
    if w:
        w.stream.status = "SIMULATED" if w.stream.is_simulated else "ONLINE"
    return {"reset": True}
