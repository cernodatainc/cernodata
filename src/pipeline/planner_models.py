"""
src/pipeline/planner_models.py

Backwards-compatibility shim forwarding to src.pipeline.planner.models.
"""

from __future__ import annotations

from src.pipeline.planner.models import (
    DocumentPlan,
    IngestionConfig,
    PlannerCriteria,
)

__all__ = [
    "DocumentPlan",
    "IngestionConfig",
    "PlannerCriteria",
]
