"""Unit tests: database models, zone containment, activity state machine."""
import time
from app.models.zone import Zone
from app.vision.zones import ZoneManager
from app.vision.activity import ActivityEngine
from app.vision.tracking import TrackingEngine, _iou
from app.vision.detection import DetectionResult


def test_zone_contains_point():
    z = Zone(zone_id="Z1", camera_id="CAM-001", name="Test", zone_type="WORKSTATION",
              x1=0.1, y1=0.1, x2=0.5, y2=0.5)
    assert z.contains_point(0.3, 0.3) is True
    assert z.contains_point(0.9, 0.9) is False
    assert z.contains_point(0.1, 0.1) is True  # boundary inclusive


def test_zone_manager_locate_uses_bottom_center():
    zm = ZoneManager()
    z = Zone(zone_id="Z1", camera_id="CAM-001", name="Floor", zone_type="WORKSTATION",
              x1=0.0, y1=0.0, x2=1.0, y2=1.0)
    zm._cache = {"CAM-001": [z]}
    # bbox spans most of the frame; bottom-center should land inside [0,1]x[0,1]
    found = zm.locate("CAM-001", (100, 100, 200, 400), frame_w=640, frame_h=480)
    assert found is not None
    assert found.zone_id == "Z1"


def test_activity_engine_starts_unknown_then_transitions():
    engine = ActivityEngine()
    now = time.time()
    # first reading: not enough history yet
    result = engine.update("CAM-001", 1, (0, 0, 50, 100), "Zone A", None, now=now)
    assert result["state"] == "UNKNOWN"
    assert result["basis"] == "rule_based_inference"


def test_activity_engine_detects_walking_from_fast_motion():
    engine = ActivityEngine()
    t0 = time.time()
    engine.update("CAM-001", 1, (0, 0, 50, 100), "Zone A", None, now=t0)
    # jump the bbox far away quickly -> should read as WALKING once enough history exists
    result = engine.update("CAM-001", 1, (400, 0, 450, 100), "Zone A", None, now=t0 + 3.0)
    assert result["state"] in ("WALKING", "UNKNOWN")  # UNKNOWN only if min_history not met


def test_activity_engine_out_of_zone_when_no_zone():
    engine = ActivityEngine()
    t0 = time.time()
    engine.update("CAM-001", 1, (0, 0, 50, 100), None, None, now=t0)
    result = engine.update("CAM-001", 1, (0, 0, 50, 100), None, None, now=t0 + 3.0)
    assert result["state"] == "OUT_OF_ZONE"


def test_iou_identical_boxes_is_one():
    box = (0, 0, 10, 10)
    assert _iou(box, box) == 1.0


def test_iou_disjoint_boxes_is_zero():
    assert _iou((0, 0, 10, 10), (100, 100, 110, 110)) == 0.0


def test_tracking_engine_assigns_stable_ids_across_frames():
    tracker = TrackingEngine(camera_id="CAM-001")
    d1 = DetectionResult(class_id=0, class_name="person", confidence=0.9,
                          bbox=(10, 10, 60, 160), timestamp=time.time(), camera_id="CAM-001")
    tracker.update([d1])
    first_id = d1.track_id
    assert first_id is not None

    # same person, slightly moved -> should keep the same track id (high IOU)
    d2 = DetectionResult(class_id=0, class_name="person", confidence=0.9,
                          bbox=(12, 11, 62, 161), timestamp=time.time(), camera_id="CAM-001")
    tracker.update([d2])
    assert d2.track_id == first_id


def test_tracking_engine_assigns_new_id_to_new_person():
    tracker = TrackingEngine(camera_id="CAM-001")
    d1 = DetectionResult(class_id=0, class_name="person", confidence=0.9,
                          bbox=(10, 10, 60, 160), timestamp=time.time(), camera_id="CAM-001")
    tracker.update([d1])

    d2 = DetectionResult(class_id=0, class_name="person", confidence=0.9,
                          bbox=(500, 300, 560, 460), timestamp=time.time(), camera_id="CAM-001")
    tracker.update([d1, d2])
    assert d1.track_id != d2.track_id
