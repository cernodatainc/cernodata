"""
src/pipeline/planner_models.py

Execution plan data model and serialization routines.
"""

import os
import json
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Dict, Any, List


@dataclass
class DocumentPlan:
    document_path: str
    taxonomy: str
    hardware: str
    target: str
    security: str
    language: str
    target_threshold: float
    primary_preset: str
    fallback_queue: List[Dict[str, Any]]
    preset_order: List[str]
    suggested_order: List[str]
    overridden: bool
    scores: Dict[str, float]
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save(self, output_path: str = os.path.join("output", "plan.json")) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        return output_path

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentPlan":
        return cls(
            document_path=data.get("document_path", ""),
            taxonomy=data.get("taxonomy", "general_text"),
            hardware=data.get("hardware", "low_spec_cpu"),
            target=data.get("target", "high_precision_structure"),
            security=data.get("security", "air_gapped_local"),
            language=data.get("language", "en"),
            target_threshold=float(data.get("target_threshold", 0.82)),
            primary_preset=data.get("primary_preset", "docling_fast"),
            fallback_queue=data.get("fallback_queue", []),
            preset_order=data.get("preset_order", ["docling_fast"]),
            suggested_order=data.get("suggested_order", ["docling_fast"]),
            overridden=bool(data.get("overridden", False)),
            scores=data.get("scores", {}),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat())
        )

    @classmethod
    def load(cls, file_path: str) -> "DocumentPlan":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
