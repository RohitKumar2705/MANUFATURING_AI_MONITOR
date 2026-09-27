"""API endpoint smoke tests using FastAPI's TestClient (no real camera threads)."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    # Import app fresh; startup event will seed the (test) DB and try to start
    # camera workers, which will safely fall back to SIMULATED CAMERA since
    # there is no webcam in the test environment.
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_dashboard_summary(client):
    r = client.get("/api/dashboard/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["cameras_total"] == 5
    assert "cameras" in data


def test_list_cameras(client):
    r = client.get("/api/cameras")
    assert r.status_code == 200
    cams = r.json()
    assert len(cams) == 5
    assert {c["camera_id"] for c in cams} == {"CAM-001", "CAM-002", "CAM-003", "CAM-004", "CAM-005"}


def test_list_workers(client):
    r = client.get("/api/workers")
    assert r.status_code == 200
    workers = r.json()
    assert len(workers) == 8
    assert workers[0]["worker_id"].startswith("EMP-")


def test_camera_config_requires_admin(client):
    r = client.post("/api/cameras", json={
        "camera_id": "CAM-099", "name": "Test Cam", "location": "Nowhere",
        "source": "0", "type": "webcam",
    })
    assert r.status_code == 401


def test_login_then_create_camera(client):
    r = client.post("/api/dashboard/login", json={"username": "admin", "password": "novatech123"})
    assert r.status_code == 200

    r2 = client.post("/api/cameras", json={
        "camera_id": "CAM-099", "name": "Test Cam", "location": "Nowhere",
        "source": "0", "type": "webcam", "enabled": False,
    })
    assert r2.status_code == 200
    assert r2.json()["camera_id"] == "CAM-099"

    # cleanup
    r3 = client.delete("/api/cameras/CAM-099")
    assert r3.status_code == 200


def test_login_wrong_password_rejected(client):
    r = client.post("/api/dashboard/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_dashboard_page_loads(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"NovaTech" in r.content


def test_alerts_endpoint(client):
    r = client.get("/api/alerts")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_demo_simulate_idle(client):
    r = client.post("/api/demo/simulate/idle", params={"camera_id": "CAM-001", "worker_id": "EMP-001"})
    assert r.status_code == 200
    body = r.json()
    assert body["triggered"] == "idle"
    assert body["alert"]["simulated"] is True
