"""
ActivityEngine (spec sections 12, 13, 55).

Deliberately explainable / rule-based, NOT "person detected = working".
Combines:
  - bounding-box centroid movement (speed, px/sec)
  - pose keypoint movement, when a pose reading is available
  - whether the worker is inside a workstation zone at all
  - short temporal history (a rolling window, not single-frame snapshots)

States: WORKING, IDLE (reported to the user as "Potential Idle" per spec
section 13 wording), WALKING, UNKNOWN, OUT_OF_ZONE.

Every output carries `basis` = "rule_based inference" (never a raw model
confidence, per spec section 45) plus a heuristic 0-1 confidence score that
reflects how much motion evidence was available - not a calibrated
probability.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from collections import deque
from app.core.config import settings


@dataclass
class _TrackHistory:
    positions: deque = field(default_factory=lambda: deque(maxlen=150))   # (t, cx, cy)
    pose_history: deque = field(default_factory=lambda: deque(maxlen=30))  # (t, keypoints)
    state: str = "UNKNOWN"
    state_since: float = field(default_factory=time.time)
    first_seen: float = field(default_factory=time.time)
    last_zone: str | None = None


class ActivityEngine:
    def __init__(self):
        # key = (camera_id, track_id) -> _TrackHistory
        self._tracks: dict[tuple[str, int], _TrackHistory] = {}

    def _key(self, camera_id: str, track_id: int):
        return (camera_id, track_id)

    def _get(self, camera_id: str, track_id: int) -> _TrackHistory:
        k = self._key(camera_id, track_id)
        if k not in self._tracks:
            self._tracks[k] = _TrackHistory()
        return self._tracks[k]

    def drop_stale(self, active_keys: set[tuple[str, int]]):
        for k in list(self._tracks.keys()):
            if k not in active_keys:
                del self._tracks[k]

    def update(
        self,
        camera_id: str,
        track_id: int,
        bbox: tuple[float, float, float, float],
        zone_name: str | None,
        pose_keypoints: list | None,
        now: float | None = None,
    ) -> dict:
        now = now or time.time()
        th = self._get(camera_id, track_id)

        x1, y1, x2, y2 = bbox
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        th.positions.append((now, cx, cy))
        if pose_keypoints:
            th.pose_history.append((now, pose_keypoints))
        th.last_zone = zone_name

        history_span = now - th.first_seen
        if history_span < settings.min_history_seconds:
            new_state, confidence, evidence = "UNKNOWN", 0.2, "insufficient temporal history"
        elif zone_name is None:
            new_state, confidence, evidence = "OUT_OF_ZONE", 0.6, "not inside any configured workstation zone"
        else:
            new_state, confidence, evidence = self._infer_state(th, now)

        if new_state != th.state:
            th.state = new_state
            th.state_since = now

        duration_in_state = round(now - th.state_since, 1)

        return {
            "state": th.state,
            "confidence": confidence,
            "basis": "rule_based_inference",
            "evidence": evidence,
            "duration_in_state_seconds": duration_in_state,
            "zone": zone_name,
        }

    def _speed_px_per_sec(self, th: _TrackHistory, window_seconds: float = 3.0) -> float:
        now = th.positions[-1][0]
        pts = [p for p in th.positions if now - p[0] <= window_seconds]
        if len(pts) < 2:
            return 0.0
        (t0, x0, y0) = pts[0]
        (t1, x1, y1) = pts[-1]
        dt = max(t1 - t0, 1e-3)
        dist = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        return dist / dt

    def _pose_motion(self, th: _TrackHistory, window_seconds: float = 3.0) -> float:
        if len(th.pose_history) < 2:
            return 0.0
        now = th.pose_history[-1][0]
        recent = [p for p in th.pose_history if now - p[0] <= window_seconds]
        if len(recent) < 2:
            return 0.0
        total = 0.0
        count = 0
        for i in range(1, len(recent)):
            _, kb = recent[i]
            _, ka = recent[i - 1]
            if not ka or not kb or len(ka) != len(kb):
                continue
            for (xa, ya, ca), (xb, yb, cb) in zip(ka, kb):
                if ca > 0.3 and cb > 0.3:
                    total += ((xa - xb) ** 2 + (ya - yb) ** 2) ** 0.5
                    count += 1
        return total / count if count else 0.0

    def _infer_state(self, th: _TrackHistory, now: float) -> tuple[str, float, str]:
        speed = self._speed_px_per_sec(th)
        pose_motion = self._pose_motion(th)

        if speed >= settings.walking_speed_threshold:
            return "WALKING", min(0.9, 0.5 + speed / 100), f"bbox centroid speed {speed:.1f}px/s exceeds walking threshold"

        has_motion = speed >= settings.working_motion_threshold or pose_motion >= 2.0
        if has_motion:
            conf = min(0.85, 0.4 + (speed + pose_motion) / 60)
            return "WORKING", conf, f"detected movement (bbox speed {speed:.1f}px/s, pose motion {pose_motion:.1f}px)"

        # near-stationary: measure how long the track has been in a low-motion state
        idle_duration = now - th.state_since if th.state in ("IDLE", "WORKING", "UNKNOWN") else 0.0

        if th.state == "IDLE" or idle_duration >= settings.idle_threshold:
            conf = min(0.85, 0.5 + idle_duration / 300)
            return "IDLE", conf, f"near-stationary for ~{idle_duration:.0f}s (no significant bbox/pose motion)"

        # low motion but not yet past threshold - still call it WORKING but low confidence
        return "WORKING", 0.35, "low motion detected; below idle threshold so not yet flagged"


activity_engine = ActivityEngine()
