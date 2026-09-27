"""Unit tests: rule engine / alert cooldown, process monitor step machine."""
import time
from app.intelligence.alert_manager import AlertManager
from app.core.database import SessionLocal
from app.models.process import Process
from app.intelligence.process_monitor import ProcessMonitor, STEP_DWELL_SECONDS


def test_alert_cooldown_blocks_duplicate_alert_immediately():
    mgr = AlertManager()
    a1 = mgr.raise_alert(camera_id="CAM-001", worker_id="EMP-001", alert_type="Potential Idle",
                          severity="MEDIUM", message="idle 1", cooldown_seconds=5)
    a2 = mgr.raise_alert(camera_id="CAM-001", worker_id="EMP-001", alert_type="Potential Idle",
                          severity="MEDIUM", message="idle 2", cooldown_seconds=5)
    assert a1 is not None
    assert a2 is None  # blocked by cooldown


def test_alert_cooldown_allows_after_expiry():
    mgr = AlertManager()
    a1 = mgr.raise_alert(camera_id="CAM-002", worker_id="EMP-002", alert_type="Potential Idle",
                          severity="MEDIUM", message="idle 1", cooldown_seconds=0.2)
    time.sleep(0.3)
    a2 = mgr.raise_alert(camera_id="CAM-002", worker_id="EMP-002", alert_type="Potential Idle",
                          severity="MEDIUM", message="idle 2", cooldown_seconds=0.2)
    assert a1 is not None
    assert a2 is not None


def test_alert_different_worker_not_blocked_by_others_cooldown():
    mgr = AlertManager()
    a1 = mgr.raise_alert(camera_id="CAM-003", worker_id="EMP-001", alert_type="Potential Idle",
                          severity="MEDIUM", message="idle", cooldown_seconds=999)
    a2 = mgr.raise_alert(camera_id="CAM-003", worker_id="EMP-003", alert_type="Potential Idle",
                          severity="MEDIUM", message="idle", cooldown_seconds=999)
    assert a1 is not None
    assert a2 is not None


def test_process_monitor_advances_step_after_dwell(monkeypatch):
    db = SessionLocal()
    try:
        proc = Process(process_id="TEST_PROC", name="Test Process", workstation="Test Zone",
                        camera_id="CAM-TEST", steps=["step_a", "step_b", "step_c"])
        db.merge(proc)
        db.commit()
    finally:
        db.close()

    monitor = ProcessMonitor()
    # patch the module-level dwell constant used inside process_monitor.update via monkeypatch
    import app.intelligence.process_monitor as pm_module
    monkeypatch.setattr(pm_module, "STEP_DWELL_SECONDS", 0.05)

    state = monitor.update("CAM-TEST", "EMP-999", "Test Zone", "WORKING")
    assert state is not None
    assert state["process_status"] == "IN_PROGRESS"
    assert state["current_step_index"] == 0

    time.sleep(0.1)
    state2 = monitor.update("CAM-TEST", "EMP-999", "Test Zone", "WORKING")
    assert state2["current_step_index"] >= 1
    assert state2["basis"] == "heuristic_demo_progression"


def test_process_monitor_returns_none_without_matching_process():
    monitor = ProcessMonitor()
    result = monitor.update("CAM-999", "EMP-001", "Nonexistent Zone", "WORKING")
    assert result is None
