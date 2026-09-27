from sqlalchemy import Column, String, Integer, Boolean, Float
from app.core.database import Base


class Rule(Base):
    __tablename__ = "rules"

    rule_id = Column(String, primary_key=True)   # e.g. "RULE-001"
    name = Column(String, nullable=False)
    description = Column(String, default="")
    condition = Column(String, nullable=False)    # internal key the RuleEngine matches on
    severity = Column(String, default="MEDIUM")
    alert_type = Column(String, nullable=False)
    enabled = Column(Boolean, default=True)
    cooldown_seconds = Column(Float, default=45.0)

    def to_dict(self):
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "condition": self.condition,
            "severity": self.severity,
            "alert_type": self.alert_type,
            "enabled": self.enabled,
            "cooldown_seconds": self.cooldown_seconds,
        }
