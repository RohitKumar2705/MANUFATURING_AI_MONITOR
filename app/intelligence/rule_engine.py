"""
RuleEngine (spec section 17).

Rules themselves are stored in the `rules` DB table (seeded on first run,
editable later) so behavior isn't hard-coded. This class evaluates the
built-in rule *conditions* it knows how to check (idle duration, restricted
zone entry, missing PPE, process deviation) against each frame's pipeline
output, and asks the AlertManager to raise an alert - which itself applies
the per-rule cooldown so we don't spam duplicate alerts every frame.
"""
from __future__ import annotations
from app.core.database import SessionLocal
from app.models.rule import Rule
from app.core.config import settings
from app.intelligence.alert_manager import alert_manager


class RuleEngine:
    def __init__(self):
        self._rules_cache: dict[str, Rule] = {}
        self.reload()

    def reload(self):
        db = SessionLocal()
        try:
            rules = db.query(Rule).filter(Rule.enabled == True).all()  # noqa: E712
            self._rules_cache = {r.condition: r for r in rules}
        except Exception:
            # DB/tables may not exist yet (e.g. called at import time before
            # init_db() has run) - fall back to built-in defaults silently;
            # startup() calls reload() again once the DB is ready.
            self._rules_cache = {}
        finally:
            db.close()

    def _rule(self, condition: str) -> Rule | None:
        return self._rules_cache.get(condition)

    def evaluate_worker(self, camera_id: str, worker_id: str | None, track_id: int,
                         zone_name: str | None, zone_type: str | None,
                         activity: dict, ppe_status: dict | None, frame=None):
        alerts_raised = []
        display_worker = worker_id or f"UNTRACKED-{track_id}"

        # RULE-001: restricted zone entry
        if zone_type == "RESTRICTED":
            rule = self._rule("restricted_zone_entry")
            severity = rule.severity if rule else "CRITICAL"
            cooldown = rule.cooldown_seconds if rule else settings.restricted_zone_cooldown
            a = alert_manager.raise_alert(
                camera_id=camera_id, worker_id=worker_id, alert_type="Restricted Zone",
                severity=severity,
                message=f"Worker {display_worker} entered restricted zone '{zone_name}'",
                confidence=activity.get("confidence"), basis="rule_based",
                cooldown_seconds=cooldown, frame=frame,
            )
            if a:
                alerts_raised.append(a)

        # RULE-002 / RULE-003: idle thresholds
        if activity.get("state") == "IDLE":
            duration = activity.get("duration_in_state_seconds", 0)
            if duration >= settings.critical_idle_threshold:
                rule = self._rule("idle_critical")
                a = alert_manager.raise_alert(
                    camera_id=camera_id, worker_id=worker_id, alert_type="Potential Idle",
                    severity=(rule.severity if rule else "HIGH"),
                    message=f"Potential idle activity detected for worker {display_worker} "
                            f"(duration {int(duration)}s, exceeds critical threshold)",
                    confidence=activity.get("confidence"), basis="rule_based",
                    cooldown_seconds=(rule.cooldown_seconds if rule else settings.idle_critical_cooldown),
                    frame=frame,
                )
                if a:
                    alerts_raised.append(a)
            elif duration >= settings.idle_threshold:
                rule = self._rule("idle_warning")
                a = alert_manager.raise_alert(
                    camera_id=camera_id, worker_id=worker_id, alert_type="Potential Idle",
                    severity=(rule.severity if rule else "MEDIUM"),
                    message=f"Potential idle activity detected for worker {display_worker} "
                            f"(duration {int(duration)}s)",
                    confidence=activity.get("confidence"), basis="rule_based",
                    cooldown_seconds=(rule.cooldown_seconds if rule else settings.idle_warning_cooldown),
                    frame=frame,
                )
                if a:
                    alerts_raised.append(a)

        # RULE-004: PPE violation (only if a real PPE model is configured)
        if ppe_status:
            missing = [k for k, v in ppe_status.items() if v == "MISSING"]
            if missing:
                rule = self._rule("ppe_violation")
                a = alert_manager.raise_alert(
                    camera_id=camera_id, worker_id=worker_id, alert_type="PPE Violation",
                    severity=(rule.severity if rule else "HIGH"),
                    message=f"Worker {display_worker} missing PPE: {', '.join(missing)}",
                    basis="model_inference",
                    cooldown_seconds=(rule.cooldown_seconds if rule else settings.alert_default_cooldown),
                    frame=frame,
                )
                if a:
                    alerts_raised.append(a)

        return alerts_raised

    def evaluate_process(self, camera_id: str, worker_id: str | None, process_state: dict | None):
        if not process_state:
            return None
        if process_state.get("process_status") == "DEVIATION":
            rule = self._rule("process_deviation")
            return alert_manager.raise_alert(
                camera_id=camera_id, worker_id=worker_id, alert_type="Process Deviation",
                severity=(rule.severity if rule else "MEDIUM"),
                message=f"Process '{process_state.get('process_name')}' shows no progress - "
                        f"possible skipped/stalled step at '{process_state.get('current_step_name')}'",
                basis="rule_based",
                cooldown_seconds=(rule.cooldown_seconds if rule else settings.alert_default_cooldown),
            )
        return None

    def evaluate_camera_offline(self, camera_id: str, camera_name: str):
        rule = self._rule("camera_offline")
        return alert_manager.raise_alert(
            camera_id=camera_id, worker_id=None, alert_type="Camera Offline",
            severity=(rule.severity if rule else "HIGH"),
            message=f"Camera '{camera_name}' ({camera_id}) appears disconnected",
            basis="rule_based",
            cooldown_seconds=(rule.cooldown_seconds if rule else 120),
        )


rule_engine = RuleEngine()
