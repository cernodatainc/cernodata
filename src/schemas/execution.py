"""
src/schemas/execution.py

Pydantic contract schemas for pipeline execution results (plan_execution_result.json).
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from src.schemas.decision import DecisionTreeSchema
from src.schemas.dom import DocumentDOMSchema
from src.schemas.plan import DocumentPlanSchema
from src.schemas.violations import QualityViolationSchema


class PipelineExecutionResultSchema(BaseModel):
    """Canonical contract for pipeline execution results across orchestrator seams."""

    model_config = ConfigDict(extra="ignore")

    plan: Optional[DocumentPlanSchema] = None
    decision: Optional[DecisionTreeSchema] = None
    dom: Optional[DocumentDOMSchema] = None
    violations: List[QualityViolationSchema] = Field(default_factory=list)
    total_violations: int = 0
    chosen_preset: Optional[str] = None
    status: str = "ACCEPT"
    overall_confidence: Optional[float] = None
    dom_json_path: Optional[str] = None
    violations_json_path: Optional[str] = None
    plan_result_path: Optional[str] = None
    html_viewer_path: Optional[str] = None
    rendered_images: List[str] = Field(default_factory=list)
