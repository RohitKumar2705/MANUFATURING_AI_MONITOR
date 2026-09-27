"""
Abstract model interfaces (spec section 62 / 63).

Keeping these as small ABCs means a custom manufacturing YOLO model, a real
PPE model, or a future action-recognition model (VideoMAE / SlowFast / X3D /
MoViNet / RTMPose) can be dropped in later without touching the pipeline
code that calls them.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class DetectionModel(ABC):
    @abstractmethod
    def predict(self, frame) -> list[dict]:
        """Return a list of DetectionResult-shaped dicts for one frame."""
        raise NotImplementedError


class ActivityModel(ABC):
    @abstractmethod
    def predict(self, frame_history: list, detections: list[dict]) -> dict:
        """Return an activity classification dict for a tracked person."""
        raise NotImplementedError


class PPEModel(ABC):
    @abstractmethod
    def predict(self, frame, person_bbox) -> dict:
        """Return PPE-item -> status for the cropped person region."""
        raise NotImplementedError

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        raise NotImplementedError
