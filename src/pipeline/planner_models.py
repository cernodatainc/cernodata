"""
src/pipeline/planner_models.py

Execution plan data model and serialization routines.
"""

import os
import json
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional

from src.utils import mkdirs


@dataclass
class PlannerCriteria:
    """Strongly-typed criteria inputs for preset suitability ranking."""
    taxonomy: str = "general_text"
    target: str = "high_precision_structure"
    security: str = "air_gapped_local"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlannerCriteria":
        return cls(
            taxonomy=str(data.get("taxonomy", "general_text")),
            target=str(data.get("target", "high_precision_structure")),
            security=str(data.get("security", "air_gapped_local")),
        )

    def values(self) -> List[str]:
        """Returns the list of criteria values for weight matching."""
        return [self.taxonomy, self.target, self.security]


@dataclass
class IngestionConfig:
    """Strongly-typed pipeline configuration for document parsing and quality evaluation."""
    target_threshold: float = 0.82
    language: Optional[str] = "en"
    preset: str = "docling_fast"
    align_skew: bool = True
    visualize: bool = True
    output_dir: str = "output"
    ocr_scale: Optional[float] = None
    force_full_page_ocr: bool = False
    do_table_structure: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IngestionConfig":
        return cls(
            target_threshold=float(data.get("target_threshold", 0.82)),
            language=data.get("language"),
            preset=str(data.get("preset", "docling_fast")),
            align_skew=bool(data.get("align_skew", True)),
            visualize=bool(data.get("visualize", True)),
            output_dir=str(data.get("output_dir", "output")),
            ocr_scale=float(data["ocr_scale"]) if data.get("ocr_scale") is not None else None,
            force_full_page_ocr=bool(data.get("force_full_page_ocr", False)),
            do_table_structure=bool(data.get("do_table_structure", True)),
        )


class DocumentPlan:
    """Executable plan defining candidate preset hierarchy and quality thresholds."""
    document_path: str
    criteria: PlannerCriteria
    language: Optional[str]
    target_threshold: float
    primary_preset: str
    fallback_queue: List[Dict[str, Any]]
    preset_order: List[str]
    suggested_order: List[str]
    overridden: bool
    scores: Dict[str, float]
    created_at: str

    def __init__(
        self,
        document_path: str = "",
        criteria: Optional[PlannerCriteria] = None,
        language: Optional[str] = None,
        target_threshold: float = 0.82,
        primary_preset: str = "docling_fast",
        fallback_queue: Optional[List[Dict[str, Any]]] = None,
        preset_order: Optional[List[str]] = None,
        suggested_order: Optional[List[str]] = None,
        overridden: bool = False,
        scores: Optional[Dict[str, float]] = None,
        created_at: Optional[str] = None,
        taxonomy: Optional[str] = None,
        target: Optional[str] = None,
        security: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.document_path = document_path
        if criteria is not None:
            self.criteria = criteria
        else:
            self.criteria = PlannerCriteria(
                taxonomy=taxonomy or "general_text",
                target=target or "high_precision_structure",
                security=security or "air_gapped_local",
            )
        self.language = language
        self.target_threshold = target_threshold
        self.primary_preset = primary_preset
        self.fallback_queue = fallback_queue or []
        self.preset_order = preset_order or [primary_preset]
        self.suggested_order = suggested_order or [primary_preset]
        self.overridden = overridden
        self.scores = scores or {}
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    @property
    def taxonomy(self) -> str:
        return self.criteria.taxonomy

    @property
    def target(self) -> str:
        return self.criteria.target

    @property
    def security(self) -> str:
        return self.criteria.security

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_path": self.document_path,
            "criteria": self.criteria.to_dict(),
            "taxonomy": self.criteria.taxonomy,
            "target": self.criteria.target,
            "security": self.criteria.security,
            "language": self.language,
            "target_threshold": self.target_threshold,
            "primary_preset": self.primary_preset,
            "fallback_queue": self.fallback_queue,
            "preset_order": self.preset_order,
            "suggested_order": self.suggested_order,
            "overridden": self.overridden,
            "scores": self.scores,
            "created_at": self.created_at,
        }

    def to_ingestion_config(
        self,
        align_skew: bool = True,
        visualize: bool = True,
        output_dir: str = "output"
    ) -> IngestionConfig:
        """Derives a strongly-typed IngestionConfig from this execution plan."""
        return IngestionConfig(
            target_threshold=self.target_threshold,
            language=self.language,
            preset=self.primary_preset,
            align_skew=align_skew,
            visualize=visualize,
            output_dir=output_dir,
        )

    def save(self, output_path: str = os.path.join("output", "plan.json")) -> str:
        mkdirs(os.path.dirname(output_path))
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        return output_path

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentPlan":
        if "criteria" in data and isinstance(data["criteria"], dict):
            criteria = PlannerCriteria.from_dict(data["criteria"])
        else:
            criteria = PlannerCriteria.from_dict(data)

        return cls(
            document_path=data.get("document_path", ""),
            criteria=criteria,
            language=data.get("language"),
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

