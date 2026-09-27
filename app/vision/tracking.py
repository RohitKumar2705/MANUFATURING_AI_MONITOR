"""
TrackingEngine (spec architecture section 3: a component separate from
DetectionEngine).

Each camera owns its OWN TrackingEngine instance. This is deliberate: the
shared DetectionEngine only runs stateless `.predict()` calls (safe to call
from multiple threads), while all mutable "which box belongs to which
worker ID" state lives here, scoped per camera. That guarantees Worker 001
on Camera 1 can never collide with Worker 001 on Camera 4 just because they
happened to share a model instance.

Algorithm: greedy IOU matching between this frame's detections and the
previous frame's live tracks (a simple, dependency-free "IOU tracker" -
similar in spirit to ByteTrack/SORT but without a Kalman filter, which is
adequate for a slow-moving factory-floor demo). Tracks that go unmatched
for longer than `track_timeout_seconds` are dropped so IDs don't grow
unbounded.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from app.core.config import settings


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


@dataclass
class _Track:
    track_id: int
    bbox: tuple[float, float, float, float]
    last_seen: float = field(default_factory=time.time)


class TrackingEngine:
    """One instance per camera - NOT a shared singleton."""

    def __init__(self, camera_id: str, iou_threshold: float = 0.3):
        self.camera_id = camera_id
        self.iou_threshold = iou_threshold
        self._tracks: dict[int, _Track] = {}
        self._next_id = 1

    def update(self, detections: list) -> list:
        """detections: list of DetectionResult (person-class only, track_id
        ignored/None on input). Returns the same list with .track_id filled
        in, mutating in place and returning it for convenience."""
        now = time.time()
        timeout = settings.get("tracking.track_timeout_seconds", 5)

        unmatched_dets = list(range(len(detections)))
        unmatched_tracks = set(self._tracks.keys())
        matches: list[tuple[int, int]] = []  # (det_idx, track_id)

        # greedy best-IOU matching
        pairs = []
        for di in unmatched_dets:
            for tid in unmatched_tracks:
                score = _iou(detections[di].bbox, self._tracks[tid].bbox)
                if score >= self.iou_threshold:
                    pairs.append((score, di, tid))
        pairs.sort(key=lambda x: -x[0])

        used_dets, used_tracks = set(), set()
        for score, di, tid in pairs:
            if di in used_dets or tid in used_tracks:
                continue
            matches.append((di, tid))
            used_dets.add(di)
            used_tracks.add(tid)

        # apply matches
        for di, tid in matches:
            detections[di].track_id = tid
            self._tracks[tid].bbox = detections[di].bbox
            self._tracks[tid].last_seen = now

        # new tracks for unmatched detections
        for di in unmatched_dets:
            if di in used_dets:
                continue
            tid = self._next_id
            self._next_id += 1
            detections[di].track_id = tid
            self._tracks[tid] = _Track(track_id=tid, bbox=detections[di].bbox, last_seen=now)

        # drop stale tracks
        for tid in list(self._tracks.keys()):
            if now - self._tracks[tid].last_seen > timeout:
                del self._tracks[tid]

        return detections

    def active_keys(self) -> set[int]:
        return set(self._tracks.keys())
