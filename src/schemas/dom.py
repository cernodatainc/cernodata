"""
src/schemas/dom.py

Pydantic contract schemas for document DOM representations (document_dom.json).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class BoundingBoxSchema(BaseModel):
    """Normalized spatial coordinates for layout bounding boxes."""

    model_config = ConfigDict(extra="ignore")

    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0

    @classmethod
    def from_raw(cls, raw: Any) -> BoundingBoxSchema:
        """Parses coordinate representation from dict, list, or existing schema."""
        if isinstance(raw, BoundingBoxSchema):
            return raw
        if isinstance(raw, (list, tuple)) and len(raw) >= 4:
            return cls(x0=float(raw[0]), y0=float(raw[1]), x1=float(raw[2]), y1=float(raw[3]))
        if isinstance(raw, dict):
            return cls(
                x0=float(raw.get("x0", 0.0)),
                y0=float(raw.get("y0", 0.0)),
                x1=float(raw.get("x1", 0.0)),
                y1=float(raw.get("y1", 0.0)),
            )
        return cls()


class DOMNodeSchema(BaseModel):
    """Canonical schema for individual document intermediate representation nodes."""

    model_config = ConfigDict(extra="ignore")

    node_id: str
    type: str = "paragraph"
    global_page_index: int = 1
    temp_slice_index: int = 1
    bounding_box: BoundingBoxSchema = Field(default_factory=BoundingBoxSchema)
    content: Dict[str, Any] = Field(default_factory=dict)
    template_hint_applied: Optional[str] = None
    violations: List[Dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _validate_bounding_box(cls, data: Any) -> Any:
        if isinstance(data, dict) and "bounding_box" in data:
            data["bounding_box"] = BoundingBoxSchema.from_raw(data["bounding_box"])
        return data


class DocumentDOMSchema(BaseModel):
    """Canonical schema for full document DOM trees exported to document_dom.json."""

    model_config = ConfigDict(extra="ignore")

    document_id: str
    source_filename: str
    total_pages: int
    nodes: List[DOMNodeSchema] = Field(default_factory=list)
