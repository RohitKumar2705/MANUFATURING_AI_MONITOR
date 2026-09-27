"""
CameraManager: owns one CameraStream + processing loop per configured
camera. Each camera runs in its own thread (spec section 56) so a failed
or stalled camera never blocks the other four. Runs detection+tracking at
a capped `inference_fps` (spec section 31) and re-uses the tracker's own
persistence between inference calls for smoothness, while the *broadcast*
of encoded JPEG frames to the dashboard runs at a friendlier UI rate.
"""
from __future__ import annotations

import cv2
import time
import threading
from datetime import datetime, timezone

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging_setup import logger
from app.vision.camera_stream import CameraStream
from app.vision.detection import DetectionEngine
from app.vision.tracking import TrackingEngine
from app.vision.pose import PoseEngine
from app.vision.ppe import PPEDetector
from app.vision.zones import zone_manager
from app.vision.activity import activity_engine
from app.models.camera import Camera
from app.services.worker_service import worker_manager
from app.services.event_service import event_logger
from app.intelligence.rule_engine import rule_engine
from app.intelligence.process_monitor import process_monitor


ACTIVITY_COLORS = {
    "WORKING": (90, 200, 90),
    "IDLE": (0, 165, 255),
    "WALKING": (255, 200, 0),
    "UNKNOWN": (150, 150, 150),
    "OUT_OF_ZONE": (60, 60, 220),
}


class CameraWorker:
    """Runs the full pipeline for exactly one camera."""

    def __init__(self, cam_row: Camera, on_update=None):
        self.camera_id = cam_row.camera_id
        self.name = cam_row.name
        self.location = cam_row.location
        self.stream = CameraStream(
            camera_id=cam_row.camera_id,
            name=cam_row.name,
            source=cam_row.source,
            source_type=cam_row.type,
            fallback_to_synthetic=True,
        )
        self.on_update = on_update  # callback(camera_id, payload:dict)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_inference_ts = 0.0
        self.latest_jpeg: bytes | None = None
        self.latest_workers: list[dict] = []
        self._frame_lock = threading.Lock()
        self._prev_state_by_track: dict[int, str] = {}
        self._prev_zone_by_track: dict[int, str | None] = {}
        self._offline_reported = False
        self.tracker = TrackingEngine(camera_id=self.camera_id)

    def start(self):
        self.stream.start()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.stream.stop()

    def _loop(self):
        det_engine = DetectionEngine.instance()
        pose_engine = PoseEngine.instance()
        ppe_detector = PPEDetector.instance()
        min_interval = 1.0 / max(settings.inference_fps, 0.1)

        while not self._stop_event.is_set():
            frame = self.stream.read()
            if frame is None:
                time.sleep(0.1)
                continue

            h, w = frame.shape[:2]
            now = time.time()
            run_inference = (now - self._last_inference_ts) >= min_interval

            workers_payload = []
            if run_inference:
                self._last_inference_ts = now
                raw_detections = det_engine.predict_frame(frame, self.camera_id)
                person_detections = [d for d in raw_detections if d.class_name == "person"]
                detections = self.tracker.update(person_detections)

                db = SessionLocal()
                try:
                    zone_manager.reload(db)
                finally:
                    db.close()

                poses = pose_engine.predict(frame) if pose_engine.model_loaded else []

                active_keys = set()
                for d in detections:
                    active_keys.add((self.camera_id, d.track_id))

                    zone = zone_manager.locate(self.camera_id, d.bbox, w, h)
                    zone_name = zone.name if zone else None
                    zone_type = zone.zone_type if zone else None

                    # match the closest pose reading to this person's bbox (IoU-ish center distance)
                    kpts = self._match_pose(d.bbox, poses)

                    activity = activity_engine.update(
                        camera_id=self.camera_id,
                        track_id=d.track_id,
                        bbox=d.bbox,
                        zone_name=zone_name,
                        pose_keypoints=kpts,
                    )

                    ppe_status = None
                    if ppe_detector.is_configured:
                        ppe_status = ppe_detector.predict(frame, d.bbox)

                    worker_id = worker_manager.resolve(self.camera_id, d.track_id)
                    if worker_id:
                        worker_manager.update_worker_state(worker_id, self.camera_id, zone_name, activity["state"])

                    self._log_transitions(d.track_id, worker_id, zone_name, activity)

                    alerts = rule_engine.evaluate_worker(
                        camera_id=self.camera_id, worker_id=worker_id, track_id=d.track_id,
                        zone_name=zone_name, zone_type=zone_type, activity=activity,
                        ppe_status=ppe_status, frame=frame,
                    )

                    process_state = None
                    if zone_type == "WORKSTATION":
                        process_state = process_monitor.update(
                            self.camera_id, worker_id, zone_name, activity["state"]
                        )
                        rule_engine.evaluate_process(self.camera_id, worker_id, process_state)

                    workers_payload.append({
                        "track_id": d.track_id,
                        "worker_id": worker_id,
                        "bbox": d.bbox,
                        "confidence": d.confidence,
                        "zone": zone_name,
                        "zone_type": zone_type,
                        "activity": activity,
                        "ppe": ppe_status,
                        "process": process_state,
                        "alerts_raised": [a["alert_id"] for a in alerts],
                    })

                activity_engine.drop_stale(active_keys)
                worker_manager.release_stale(active_keys)
                self.latest_workers = workers_payload

                if self.on_update:
                    self.on_update(self.camera_id, {
                        "camera_id": self.camera_id,
                        "workers": workers_payload,
                        "status": self.stream.status,
                        "is_simulated": self.stream.is_simulated,
                        "fps": round(self.stream.actual_fps, 1),
                        "timestamp": datetime.utcnow().isoformat(),
                    })
            else:
                workers_payload = self.latest_workers

            annotated = self._draw_overlay(frame, workers_payload)
            ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                with self._frame_lock:
                    self.latest_jpeg = buf.tobytes()

            time.sleep(0.01)

    def _log_transitions(self, track_id: int, worker_id: str | None, zone_name: str | None, activity: dict):
        """Emit event-log rows only on actual state/zone changes (spec section 20)."""
        who = worker_id or f"Worker {track_id:03d}"

        prev_zone = self._prev_zone_by_track.get(track_id, "__none__")
        if zone_name != prev_zone:
            self._prev_zone_by_track[track_id] = zone_name
            if zone_name:
                event_logger.log_activity(
                    self.camera_id, worker_id, "ZONE_ENTER", f"{who} entered {zone_name}",
                )
            elif prev_zone not in ("__none__", None):
                event_logger.log_activity(
                    self.camera_id, worker_id, "ZONE_EXIT", f"{who} left {prev_zone}",
                )

        prev_state = self._prev_state_by_track.get(track_id)
        new_state = activity["state"]
        if prev_state and prev_state != new_state:
            event_logger.log_activity(
                self.camera_id, worker_id, "ACTIVITY_CHANGE",
                f"{who} activity changed: {prev_state} -> {new_state}",
            )
        self._prev_state_by_track[track_id] = new_state

    def _match_pose(self, bbox, poses: list[dict]) -> list | None:
        if not poses:
            return None
        x1, y1, x2, y2 = bbox
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        best, best_dist = None, 1e9
        for p in poses:
            px1, py1, px2, py2 = p["bbox"]
            pcx, pcy = (px1 + px2) / 2, (py1 + py2) / 2
            dist = ((cx - pcx) ** 2 + (cy - pcy) ** 2) ** 0.5
            if dist < best_dist:
                best_dist, best = dist, p
        if best and best_dist < 60:
            return best["keypoints"]
        return None

    def _draw_overlay(self, frame, workers_payload):
        annotated = frame.copy()
        h, w = annotated.shape[:2]

        for z in zone_manager.zones_for_camera(self.camera_id):
            x1, y1, x2, y2 = int(z.x1 * w), int(z.y1 * h), int(z.x2 * w), int(z.y2 * h)
            color = (0, 60, 220) if z.zone_type == "RESTRICTED" else (120, 120, 60)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 1)
            cv2.putText(annotated, z.name, (x1 + 4, max(14, y1 + 14)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)

        for wpl in workers_payload:
            x1, y1, x2, y2 = [int(v) for v in wpl["bbox"]]
            state = wpl["activity"]["state"]
            color = ACTIVITY_COLORS.get(state, (200, 200, 200))
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            label1 = f"Worker {wpl['track_id']:03d}"
            label2 = f"{state}  {int(wpl['confidence']*100)}%"
            cv2.rectangle(annotated, (x1, max(0, y1 - 34)), (x1 + 150, y1), color, -1)
            cv2.putText(annotated, label1, (x1 + 4, y1 - 20), cv2.FONT_HERSHEY_SIMPLEX,
                        0.42, (0, 0, 0), 1, cv2.LINE_AA)
            cv2.putText(annotated, label2, (x1 + 4, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX,
                        0.42, (0, 0, 0), 1, cv2.LINE_AA)

        tag = "SIMULATED" if self.stream.is_simulated else "LIVE"
        tag_color = (0, 210, 255) if self.stream.is_simulated else (90, 220, 90)
        cv2.putText(annotated, f"{self.name} [{tag}]", (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, tag_color, 1, cv2.LINE_AA)
        return annotated

    def get_jpeg(self) -> bytes | None:
        with self._frame_lock:
            return self.latest_jpeg


class CameraManager:
    _instance: "CameraManager | None" = None

    def __init__(self):
        self.workers: dict[str, CameraWorker] = {}
        self.update_callback = None

    @classmethod
    def instance(cls) -> "CameraManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_update_callback(self, cb):
        self.update_callback = cb

    def start_all(self, camera_rows: list[Camera]):
        for cam in camera_rows:
            if not cam.enabled:
                continue
            self.start_camera(cam)

    def start_camera(self, cam: Camera):
        if cam.camera_id in self.workers:
            self.stop_camera(cam.camera_id)
        worker = CameraWorker(cam, on_update=self.update_callback)
        worker.start()
        self.workers[cam.camera_id] = worker
        logger.info(f"Started camera worker for {cam.camera_id} ({cam.name})")

    def stop_camera(self, camera_id: str):
        w = self.workers.pop(camera_id, None)
        if w:
            w.stop()
            logger.info(f"Stopped camera worker for {camera_id}")

    def stop_all(self):
        for cid in list(self.workers.keys()):
            self.stop_camera(cid)

    def get_worker(self, camera_id: str) -> CameraWorker | None:
        return self.workers.get(camera_id)

    def status_snapshot(self) -> list[dict]:
        out = []
        for cid, w in self.workers.items():
            out.append({
                "camera_id": cid,
                "status": w.stream.status,
                "is_simulated": w.stream.is_simulated,
                "fps": round(w.stream.actual_fps, 1),
                "active_workers": len(w.latest_workers),
            })
        return out


camera_manager = CameraManager()
