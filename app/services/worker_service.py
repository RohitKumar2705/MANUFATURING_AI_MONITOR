"""
WorkerManager: maps a camera's transient YOLO tracking IDs to the demo
employee roster so the dashboard can show "EMP-002 is at Assembly Station A"
rather than an anonymous "Worker 007".

IMPORTANT (privacy, spec section 44): this is NOT facial recognition. It is
a simple first-seen/available-slot assignment against demo employee records
for prototype/demo purposes only. In a real deployment this would be
replaced by a badge/RFID/manual check-in correlation step - the mapping
itself is explicitly a simplification and is labeled as such wherever it
surfaces in the UI.
"""
from __future__ import annotations
import time
from datetime import datetime, timezone
from app.core.database import SessionLocal
from app.models.worker import Worker, WorkerSession

TRACK_TIMEOUT_SECONDS = 15


class WorkerManager:
    def __init__(self):
        # (camera_id, track_id) -> worker_id
        self._track_to_worker: dict[tuple[str, int], str] = {}
        self._worker_last_seen: dict[str, float] = {}
        self._camera_assigned: dict[str, set[str]] = {}

    def resolve(self, camera_id: str, track_id: int) -> str | None:
        """Return a demo worker_id for this (camera, track_id), assigning a
        free demo worker on first sight if one is available."""
        key = (camera_id, track_id)
        now = time.time()

        if key in self._track_to_worker:
            wid = self._track_to_worker[key]
            self._worker_last_seen[wid] = now
            return wid

        db = SessionLocal()
        try:
            all_workers = db.query(Worker).order_by(Worker.worker_id).all()
        finally:
            db.close()

        assigned_ids = set(self._track_to_worker.values())
        candidate = next((w for w in all_workers if w.worker_id not in assigned_ids), None)
        if candidate is None:
            return None

        self._track_to_worker[key] = candidate.worker_id
        self._worker_last_seen[candidate.worker_id] = now
        return candidate.worker_id

    def release_stale(self, active_keys: set[tuple[str, int]]):
        now = time.time()
        for key in list(self._track_to_worker.keys()):
            wid = self._track_to_worker[key]
            last_seen = self._worker_last_seen.get(wid, 0)
            if key not in active_keys and (now - last_seen) > TRACK_TIMEOUT_SECONDS:
                del self._track_to_worker[key]

    def update_worker_state(self, worker_id: str, camera_id: str, zone: str | None, status: str):
        db = SessionLocal()
        try:
            w = db.query(Worker).filter(Worker.worker_id == worker_id).first()
            if w:
                w.current_camera = camera_id
                w.current_zone = zone
                w.status = status
                w.last_seen = datetime.utcnow()
                db.commit()
        finally:
            db.close()


worker_manager = WorkerManager()
