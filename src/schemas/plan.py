"""
src/schemas/plan.py

Pydantic contract schemas for pipeline execution plans (plan.json).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PlannerCriteriaSchema(BaseModel):
    """Execution criteria determining preset prioritization and constraints."""

    model_config = ConfigDict(extra="ignore")

    taxonomy: str = "general_text"
    target: str = "high_precision_structure"
    security: str = "air_gapped_local"
    hardware: Optional[str] = None


class DocumentPlanSchema(BaseModel):
    """Canonical schema for execution plans produced by PresetPlanner."""

    model_config = ConfigDict(extra="ignore")

    document_path: str = ""
    criteria: PlannerCriteriaSchema = Field(default_factory=PlannerCriteriaSchema)
    taxonomy: Optional[str] = None
    target: Optional[str] = None
    security: Optional[str] = None
    hardware: Optional[str] = None
    language: Optional[str] = None
    target_threshold: float = 0.82
    primary_preset: str = "docling_fast"
    fallback_queue: List[Dict[str, Any]] = Field(default_factory=list)
    preset_order: List[str] = Field(default_factory=list)
    suggested_order: List[str] = Field(default_factory=list)
    overridden: bool = False
    scores: Dict[str, float] = Field(default_factory=dict)
    created_at: str = Field(default="")
