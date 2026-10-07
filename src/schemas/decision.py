"""
src/schemas/decision.py

Pydantic contract schemas for decision tree evaluations and attempt records (decision_tree.json).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AttemptRecordSchema(BaseModel):
    """Structured record tracking iteration history in pipeline fallback execution."""

    model_config = ConfigDict(extra="ignore")

    step: int
    preset: str
    overall_confidence: Optional[float] = None
    per_page_confidence: Optional[Dict[str, float]] = None
    status: Optional[str] = None
    is_accepted: Optional[bool] = None
    violations_count: Optional[int] = None
    action: Optional[str] = None
    reason: Optional[str] = None
    detail: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class DecisionTreeSchema(BaseModel):
    """Canonical schema for quality evaluation decision tree outputs."""

    model_config = ConfigDict(extra="ignore")

    preset_id: str = "docling_fast"
    language: Optional[str] = "en"
    detected_languages: Dict[str, Any] = Field(default_factory=dict)
    detected_language_confidences: Dict[str, Any] = Field(default_factory=dict)
    primary_detected_language: Optional[str] = "en"
    target_confidence_threshold: float = 0.82
    overall_confidence: Optional[float] = None
    per_page_confidence: Dict[str, float] = Field(default_factory=dict)
    is_accepted: bool = True
    pages_requiring_slicing: List[int] = Field(default_factory=list)
    decision_tree: Dict[str, Any] = Field(default_factory=dict)
    status: str = "ACCEPT"
    chosen_preset: Optional[str] = None
    attempts: List[AttemptRecordSchema] = Field(default_factory=list)
