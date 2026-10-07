"""
src/schemas/violations.py

Pydantic contract schemas for quality violations (quality_violations.json).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field

from src.schemas.dom import BoundingBoxSchema


class QualityViolationSchema(BaseModel):
    """Canonical schema for individual document quality violation records."""

    model_config = ConfigDict(extra="ignore")

    violation_id: str
    global_page_index: int = 1
    node_id: str = ""
    type: str = "general"
    rule_type: str = ""
    severity: str = "MEDIUM"
    detected_snippet: Optional[str] = ""
    suggestion: Optional[str] = None
    suppressed: Union[str, bool] = False
    is_fixed: Optional[bool] = False
    accepted: Optional[bool] = False
    description: str = ""
    bounding_box: Optional[Union[BoundingBoxSchema, Dict[str, float], List[float]]] = None

    def is_active(self) -> bool:
        """Determines if the violation is currently active (unsuppressed, unaccepted, unfixed)."""
        if isinstance(self.suppressed, str):
            if self.suppressed.lower() in ("true", "1"):
                return False
        elif bool(self.suppressed):
            return False
        if bool(self.accepted) or bool(self.is_fixed):
            return False
        return True


class ViolationsReportSchema(BaseModel):
    """Canonical schema for quality violations export payload."""

    model_config = ConfigDict(extra="ignore")

    document_id: Optional[str] = None
    source_filename: Optional[str] = None
    language: Optional[str] = "en"
    detected_languages: Dict[str, Any] = Field(default_factory=dict)
    primary_detected_language: Optional[str] = "en"
    total_violations: int = 0
    violations: List[QualityViolationSchema] = Field(default_factory=list)


def parse_violations_payload(raw: Any) -> List[QualityViolationSchema]:
    """
    Parses and strictly validates raw violation input into a list of QualityViolationSchema.
    Supports either list format or container report format.
    """
    if isinstance(raw, list):
        return [QualityViolationSchema.model_validate(v) for v in raw]
    if isinstance(raw, dict):
        report = ViolationsReportSchema.model_validate(raw)
        return report.violations
    return []
