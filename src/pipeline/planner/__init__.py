"""
src/pipeline/planner/__init__.py

Data-Driven Preset Planner package.
Inquires about document characteristics and system constraints, computes preset suitability
rankings, allows user override, and produces an executable execution plan.
Siloed from execution orchestrator and visual viewer.
"""

from __future__ import annotations

from src.pipeline.planner.models import (
    DocumentPlan,
    IngestionConfig,
    PlannerCriteria,
)
from src.pipeline.planner.options import (
    DEFAULT_FALLBACK_PRESET,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PORT,
    DEFAULT_PRESET_WEIGHTS,
    DEFAULT_PRIMARY_PRESET,
    DEFAULT_SECURITY,
    DEFAULT_SUITABILITY_SCORE,
    DEFAULT_TARGET,
    DEFAULT_TARGET_THRESHOLD,
    DEFAULT_TAXONOMY,
    PLANNER_DEFAULTS,
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

__all__ = [
    "DEFAULT_FALLBACK_PRESET",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_PORT",
    "DEFAULT_PRESET_WEIGHTS",
    "DEFAULT_PRIMARY_PRESET",
    "DEFAULT_SECURITY",
    "DEFAULT_SUITABILITY_SCORE",
    "DEFAULT_TARGET",
    "DEFAULT_TARGET_THRESHOLD",
    "DEFAULT_TAXONOMY",
    "DocumentPlan",
    "IngestionConfig",
    "PLANNER_DEFAULTS",
    "PlannerCriteria",
    "PresetPlanner",
    "SECURITY_OPTIONS",
    "TARGET_OPTIONS",
    "TAXONOMY_OPTIONS",
    "WIZARD_DIMENSIONS",
    "WizardDimension",
    "resolve_choice",
    "run_interactive_wizard",
]
