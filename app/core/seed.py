"""
First-run setup (spec section 50). Idempotent: safe to call on every
startup - only inserts rows that don't already exist.
"""
from __future__ import annotations
from app.core.database import SessionLocal
from app.core.logging_setup import logger
from app.models.camera import Camera
from app.models.worker import Worker
from app.models.zone import Zone
from app.models.process import Process
from app.models.rule import Rule

CAMERAS = [
    dict(camera_id="CAM-001", name="Assembly Line A", location="Assembly Station A",
         purpose="Assembly monitoring", source="0", type="webcam"),
    dict(camera_id="CAM-002", name="Assembly Line B", location="Assembly Station B",
         purpose="Assembly monitoring", source="demo/videos/cam2_assembly_b.mp4", type="video_file"),
    dict(camera_id="CAM-003", name="Quality Inspection", location="QC Station",
         purpose="Inspection monitoring", source="demo/videos/cam3_quality.mp4", type="video_file"),
    dict(camera_id="CAM-004", name="Packaging", location="Packaging Station",
         purpose="Packaging monitoring", source="demo/videos/cam4_packaging.mp4", type="video_file"),
    dict(camera_id="CAM-005", name="Warehouse / Material Handling", location="Material Handling Area",
         purpose="Worker and material movement monitoring", source="demo/videos/cam5_warehouse.mp4", type="video_file"),
]

WORKERS = [
    dict(worker_id="EMP-001", employee_code="EMP-001", name="Rahul Sharma", department="Assembly",
         shift="Day (09:00-18:00)", assigned_workstation="Assembly Station A"),
    dict(worker_id="EMP-002", employee_code="EMP-002", name="Amit Verma", department="Assembly",
         shift="Day (09:00-18:00)", assigned_workstation="Assembly Station B"),
    dict(worker_id="EMP-003", employee_code="EMP-003", name="Neha Patel", department="Quality Control",
         shift="Day (09:00-18:00)", assigned_workstation="QC Station"),
    dict(worker_id="EMP-004", employee_code="EMP-004", name="Arjun Singh", department="Packaging",
         shift="Day (09:00-18:00)", assigned_workstation="Packaging Station"),
    dict(worker_id="EMP-005", employee_code="EMP-005", name="Priya Gupta", department="Warehouse",
         shift="Day (09:00-18:00)", assigned_workstation="Material Handling Area"),
    dict(worker_id="EMP-006", employee_code="EMP-006", name="Rohan Das", department="Assembly",
         shift="Evening (18:00-02:00)", assigned_workstation="Assembly Station A"),
    dict(worker_id="EMP-007", employee_code="EMP-007", name="Anjali Singh", department="Quality Control",
         shift="Evening (18:00-02:00)", assigned_workstation="QC Station"),
    dict(worker_id="EMP-008", employee_code="EMP-008", name="Vikash Kumar", department="Warehouse",
         shift="Day (09:00-18:00)", assigned_workstation="Material Handling Area"),
]

# rectangles are normalized [x1, y1, x2, y2] in 0..1
ZONES = [
    # Camera 1 - Assembly Line A
    dict(zone_id="Z-CAM1-ASSEMBLY", camera_id="CAM-001", name="Assembly Zone", zone_type="WORKSTATION", rect=(0.10, 0.15, 0.65, 0.90)),
    dict(zone_id="Z-CAM1-TOOL", camera_id="CAM-001", name="Tool Zone", zone_type="MATERIAL", rect=(0.65, 0.15, 0.85, 0.55)),
    dict(zone_id="Z-CAM1-SAFETY", camera_id="CAM-001", name="Safety Zone", zone_type="SAFETY", rect=(0.65, 0.55, 0.85, 0.90)),
    dict(zone_id="Z-CAM1-RESTRICTED", camera_id="CAM-001", name="Restricted Zone", zone_type="RESTRICTED", rect=(0.85, 0.0, 1.0, 1.0)),

    # Camera 2 - Assembly Line B
    dict(zone_id="Z-CAM2-ASSEMBLY", camera_id="CAM-002", name="Assembly Zone", zone_type="WORKSTATION", rect=(0.10, 0.15, 0.65, 0.90)),
    dict(zone_id="Z-CAM2-TOOL", camera_id="CAM-002", name="Tool Zone", zone_type="MATERIAL", rect=(0.65, 0.15, 0.85, 0.55)),
    dict(zone_id="Z-CAM2-MATERIAL", camera_id="CAM-002", name="Material Zone", zone_type="MATERIAL", rect=(0.65, 0.55, 0.85, 0.90)),

    # Camera 3 - Quality Inspection
    dict(zone_id="Z-CAM3-INSPECT", camera_id="CAM-003", name="Inspection Zone", zone_type="WORKSTATION", rect=(0.10, 0.15, 0.60, 0.90)),
    dict(zone_id="Z-CAM3-QCTABLE", camera_id="CAM-003", name="QC Table", zone_type="INSPECTION", rect=(0.60, 0.15, 0.85, 0.55)),
    dict(zone_id="Z-CAM3-RESTRICTED", camera_id="CAM-003", name="Restricted Zone", zone_type="RESTRICTED", rect=(0.85, 0.0, 1.0, 1.0)),

    # Camera 4 - Packaging
    dict(zone_id="Z-CAM4-PACK", camera_id="CAM-004", name="Packaging Zone", zone_type="WORKSTATION", rect=(0.10, 0.15, 0.60, 0.90)),
    dict(zone_id="Z-CAM4-BOX", camera_id="CAM-004", name="Box Zone", zone_type="PACKAGING", rect=(0.60, 0.15, 0.85, 0.55)),
    dict(zone_id="Z-CAM4-FG", camera_id="CAM-004", name="Finished Goods Zone", zone_type="PACKAGING", rect=(0.60, 0.55, 0.85, 0.90)),

    # Camera 5 - Warehouse
    dict(zone_id="Z-CAM5-WAREHOUSE", camera_id="CAM-005", name="Warehouse Zone", zone_type="WORKSTATION", rect=(0.10, 0.15, 0.55, 0.90)),
    dict(zone_id="Z-CAM5-LOADING", camera_id="CAM-005", name="Loading Zone", zone_type="OTHER", rect=(0.55, 0.15, 0.75, 0.55)),
    dict(zone_id="Z-CAM5-MATERIAL", camera_id="CAM-005", name="Material Zone", zone_type="MATERIAL", rect=(0.55, 0.55, 0.75, 0.90)),
    dict(zone_id="Z-CAM5-RESTRICTED", camera_id="CAM-005", name="Restricted Zone", zone_type="RESTRICTED", rect=(0.85, 0.0, 1.0, 1.0)),
]

PROCESSES = [
    dict(process_id="ASSEMBLY_A", name="Assembly Process A", workstation="Assembly Zone", camera_id="CAM-001",
         steps=["pick_component", "place_component", "fasten_component", "inspect_component", "move_finished_component"]),
    dict(process_id="ASSEMBLY_B", name="Assembly Process B", workstation="Assembly Zone", camera_id="CAM-002",
         steps=["pick_component", "place_component", "fasten_component", "inspect_component", "move_finished_component"]),
    dict(process_id="QC_INSPECT", name="Quality Inspection Process", workstation="Inspection Zone", camera_id="CAM-003",
         steps=["receive_item", "visual_inspect", "measure_tolerance", "approve_or_reject", "log_result"]),
    dict(process_id="PACKAGING", name="Packaging Process", workstation="Packaging Zone", camera_id="CAM-004",
         steps=["receive_item", "wrap_item", "box_item", "label_box", "stage_for_shipping"]),
    dict(process_id="MATERIAL_HANDLING", name="Material Handling Process", workstation="Warehouse Zone", camera_id="CAM-005",
         steps=["receive_material", "verify_quantity", "store_material", "update_inventory"]),
]

RULES = [
    dict(rule_id="RULE-001", name="Restricted Zone Entry", description="Worker enters restricted zone",
         condition="restricted_zone_entry", severity="CRITICAL", alert_type="Restricted Zone", cooldown_seconds=60),
    dict(rule_id="RULE-002", name="Idle Warning", description="Worker has no detected activity for > idle threshold",
         condition="idle_warning", severity="MEDIUM", alert_type="Potential Idle", cooldown_seconds=60),
    dict(rule_id="RULE-003", name="Idle Critical", description="Worker remains idle beyond critical threshold",
         condition="idle_critical", severity="HIGH", alert_type="Potential Idle", cooldown_seconds=90),
    dict(rule_id="RULE-004", name="PPE Violation", description="Worker detected without required PPE",
         condition="ppe_violation", severity="HIGH", alert_type="PPE Violation", cooldown_seconds=45),
    dict(rule_id="RULE-005", name="Process Deviation", description="Process step appears skipped/stalled",
         condition="process_deviation", severity="MEDIUM", alert_type="Process Deviation", cooldown_seconds=90),
    dict(rule_id="RULE-006", name="Attendance Alert", description="Worker enters workstation outside assigned shift",
         condition="attendance_alert", severity="LOW", alert_type="Unexpected Worker", cooldown_seconds=120),
    dict(rule_id="RULE-007", name="Camera Offline", description="Camera disconnected", condition="camera_offline",
         severity="HIGH", alert_type="Camera Offline", cooldown_seconds=120),
]


def seed_all():
    db = SessionLocal()
    try:
        if db.query(Camera).count() == 0:
            for c in CAMERAS:
                db.add(Camera(**c, status="OFFLINE", fps=30.0, resolution="640x480", enabled=True))
            logger.info(f"Seeded {len(CAMERAS)} cameras")

        if db.query(Worker).count() == 0:
            for w in WORKERS:
                db.add(Worker(**w, status="OFFLINE"))
            logger.info(f"Seeded {len(WORKERS)} demo workers")

        if db.query(Zone).count() == 0:
            for z in ZONES:
                x1, y1, x2, y2 = z.pop("rect")
                db.add(Zone(**z, x1=x1, y1=y1, x2=x2, y2=y2))
            logger.info(f"Seeded {len(ZONES)} zones")

        if db.query(Process).count() == 0:
            for p in PROCESSES:
                db.add(Process(**p))
            logger.info(f"Seeded {len(PROCESSES)} processes")

        if db.query(Rule).count() == 0:
            for r in RULES:
                db.add(Rule(**r, enabled=True))
            logger.info(f"Seeded {len(RULES)} rules")

        db.commit()
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        db.rollback()
    finally:
        db.close()
