"""
src/pipeline/planner/__init__.py

Data-Driven Preset Planner package.
Inquires about document characteristics and system constraints, computes preset suitability
rankings, allows user override, and produces an executable execution plan.
"""

from __future__ import annotations

from typing import Any

from src.pipeline.planner.models import (
    DocumentPlan,
    IngestionConfig,
    PlannerCriteria,
)
from src.pipeline.planner.options import (
    DEFAULT_PRESET_WEIGHTS,
    SECURITY_OPTIONS,
    TARGET_OPTIONS,
    TAXONOMY_OPTIONS,
    WIZARD_DIMENSIONS,
    WizardDimension,
)
from src.pipeline.planner.planner import PresetPlanner
from src.pipeline.planner.wizard import (
    resolve_choice,
    run_interactive_wizard,
)


def __getattr__(name: str) -> Any:
    if name in ("DataShapeServer", "DataShapeHandler", "serve_data_shape_wizard"):
        import src.pipeline.planner.server as _server
        return getattr(_server, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DEFAULT_PRESET_WEIGHTS",
    "DataShapeHandler",
    "DataShapeServer",
    "DocumentPlan",
    "IngestionConfig",
    "PlannerCriteria",
    "PresetPlanner",
    "SECURITY_OPTIONS",
    "TARGET_OPTIONS",
    "TAXONOMY_OPTIONS",
    "WIZARD_DIMENSIONS",
    "WizardDimension",
    "resolve_choice",
    "run_interactive_wizard",
    "serve_data_shape_wizard",
]
