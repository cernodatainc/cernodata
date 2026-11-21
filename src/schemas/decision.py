"""
src/schemas/decision.py

Pydantic contract schemas for decision tree evaluations and attempt records (decision_tree.json).
"""

from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.dom.enums import DecisionStatus, PipelineAction


def _strip_none_values(data: Any) -> Any:
    """Drops keys with None values so schema field defaults apply at validation boundaries."""
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if v is not None}
    return data


def _stringify_keys(val: Any) -> Dict[str, Any]:
    """Normalizes mapping keys to strings at JSON/in-memory boundaries."""
    if isinstance(val, dict):
        return {str(k): v for k, v in val.items()}
    return {}


class AttemptRecordSchema(BaseModel):
    """Structured record tracking iteration history in pipeline fallback execution."""

    model_config = ConfigDict(extra="ignore")

    step: int = 1
    preset: str = ""
    overall_confidence: float = 1.0
    per_page_confidence: Dict[str, float] = Field(default_factory=dict)
    status: DecisionStatus = DecisionStatus.ACCEPT
    is_accepted: bool = True
    violations_count: int = 0
    action: PipelineAction = PipelineAction.ACCEPT_OUTPUT
    reason: str = ""
    detail: str = ""
    parameters: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _strip_none_defaults(cls, data: Any) -> Any:
        return _strip_none_values(data)

    @field_validator("status", mode="before")
    @classmethod
    def _coerce_status(cls, v: Any) -> DecisionStatus:
        return DecisionStatus.coerce(v)

    @field_validator("action", mode="before")
    @classmethod
    def _coerce_action(cls, v: Any) -> PipelineAction:
        return PipelineAction.coerce(v)

    @field_validator("per_page_confidence", mode="before")
    @classmethod
    def _coerce_page_keys(cls, v: Any) -> Dict[str, Any]:
        return _stringify_keys(v)


class DecisionTreeSchema(BaseModel):
    """Canonical schema for quality evaluation decision tree outputs."""

    model_config = ConfigDict(extra="ignore")

    preset_id: str = ""
    language: str = "en"
    detected_languages: Dict[str, Any] = Field(default_factory=dict)
    detected_language_confidences: Dict[str, Any] = Field(default_factory=dict)
    primary_detected_language: str = "en"
    target_confidence_threshold: float = 0.82
    overall_confidence: float = 1.0
    per_page_confidence: Dict[str, float] = Field(default_factory=dict)
    selected_layers: List[str] = Field(default_factory=list)
    layer_scores: Dict[str, float] = Field(default_factory=dict)
    per_page_layer_scores: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    is_accepted: bool = True
    pages_requiring_slicing: List[int] = Field(default_factory=list)
    decision_tree: Dict[str, Any] = Field(default_factory=dict)
    status: DecisionStatus = DecisionStatus.ACCEPT
    chosen_preset: str = ""
    attempts: List[AttemptRecordSchema] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _strip_none_defaults(cls, data: Any) -> Any:
        return _strip_none_values(data)

    @field_validator("status", mode="before")
    @classmethod
    def _coerce_status(cls, v: Any) -> DecisionStatus:
        return DecisionStatus.coerce(v)

    @field_validator(
        "detected_languages",
        "detected_language_confidences",
        "per_page_confidence",
        "per_page_layer_scores",
        mode="before",
    )
    @classmethod
    def _coerce_page_maps(cls, v: Any) -> Dict[str, Any]:
        return _stringify_keys(v)

    @model_validator(mode="after")
    def _normalize_attempts(self) -> DecisionTreeSchema:
        active_preset = self.chosen_preset or self.preset_id
        for att in self.attempts:
            if not att.preset and active_preset:
                att.preset = active_preset
            if att.preset == active_preset:
                if "overall_confidence" not in att.model_fields_set:
                    att.overall_confidence = self.overall_confidence
                if "status" not in att.model_fields_set:
                    att.status = self.status
                if "per_page_confidence" not in att.model_fields_set and self.per_page_confidence:
                    att.per_page_confidence = dict(self.per_page_confidence)
        return self
