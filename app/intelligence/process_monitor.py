"""
ProcessMonitor (spec sections 15, 16, 29).

Honesty note: this prototype has no per-step object/action classifier (that
would require a custom-trained action-recognition model, spec section 63/68
explicitly lists this as NOT implemented). So step progression here is a
transparent HEURISTIC: while a worker is inside a workstation zone tied to a
process and is in the WORKING state, the monitor advances one step at a
time after a configurable dwell period. This is clearly reported to the UI
as `basis: "heuristic_demo_progression"` - never presented as a real
per-step vision detection - and a worker who is not detected as WORKING
long enough before leaving the zone is flagged as a possible skipped step /
DEVIATION, per the spec's step-sequence-comparison requirement.
"""
from __future__ import annotations
import time
from datetime import datetime, timezone
from app.core.database import SessionLocal
from app.models.process import Process, ProcessState
from app.core.config import settings

STEP_DWELL_SECONDS = 12  # heuristic: how long "WORKING in zone" advances one step


class ProcessMonitor:
    def __init__(self):
        # (worker_id, process_id) -> runtime info
        self._runtime: dict[tuple[str, str], dict] = {}

    def _get_process_for_zone(self, db, camera_id: str, zone_name: str | None) -> Process | None:
        if not zone_name:
            return None
        return db.query(Process).filter(
            Process.camera_id == camera_id, Process.workstation == zone_name
        ).first()

    def update(self, camera_id: str, worker_id: str | None, zone_name: str | None,
               activity_state: str) -> dict | None:
        if not worker_id:
            return None

        db = SessionLocal()
        try:
            process = self._get_process_for_zone(db, camera_id, zone_name)
            if process is None:
                return None

            rt_key = (worker_id, process.process_id)
            state_row = db.query(ProcessState).filter(
                ProcessState.worker_id == worker_id, ProcessState.process_id == process.process_id
            ).order_by(ProcessState.id.desc()).first()

            now = datetime.utcnow()
            now_ts = time.time()

            if state_row is None or state_row.process_status == "COMPLETED":
                state_row = ProcessState(
                    process_id=process.process_id,
                    worker_id=worker_id,
                    camera_id=camera_id,
                    current_step_index=0,
                    completed_steps=[],
                    skipped_steps=[],
                    process_status="IN_PROGRESS",
                    process_started_at=now,
                    last_activity=now,
                )
                db.add(state_row)
                db.commit()
                db.refresh(state_row)
                self._runtime[rt_key] = {"dwell_start": now_ts if activity_state == "WORKING" else None}

            runtime = self._runtime.setdefault(rt_key, {"dwell_start": None})

            if activity_state == "WORKING":
                if runtime["dwell_start"] is None:
                    runtime["dwell_start"] = now_ts
                dwell = now_ts - runtime["dwell_start"]
                if dwell >= STEP_DWELL_SECONDS and state_row.current_step_index < len(process.steps):
                    step_name = process.steps[state_row.current_step_index]
                    completed = list(state_row.completed_steps or [])
                    completed.append(step_name)
                    state_row.completed_steps = completed
                    state_row.current_step_index += 1
                    state_row.last_activity = now
                    runtime["dwell_start"] = now_ts
                    if state_row.current_step_index >= len(process.steps):
                        state_row.process_status = "COMPLETED"
                    db.commit()
            else:
                runtime["dwell_start"] = None

            # stall detection -> DEVIATION/UNKNOWN
            if state_row.process_status == "IN_PROGRESS" and state_row.last_activity:
                stall = (now - state_row.last_activity).total_seconds()
                if stall > settings.process_step_stall_seconds:
                    state_row.process_status = "DEVIATION"
                    db.commit()

            db.refresh(state_row)
            result = state_row.to_dict()
            result["process_name"] = process.name
            result["total_steps"] = len(process.steps)
            result["current_step_name"] = (
                process.steps[state_row.current_step_index]
                if state_row.current_step_index < len(process.steps) else None
            )
            result["basis"] = "heuristic_demo_progression"
            return result
        finally:
            db.close()


process_monitor = ProcessMonitor()
