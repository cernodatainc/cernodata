"""
src/pipeline/planner/models.py

Execution plan data model and serialization routines.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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
    def from_dict(cls, data: Dict[str, Any]) -> PlannerCriteria:
        taxonomy = str(data.get("taxonomy", "general_text"))
        target = str(data.get("target", "high_precision_structure"))
        security = str(data.get("security", "air_gapped_local"))
        return cls(
            taxonomy=taxonomy,
            target=target,
            security=security,
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
    def from_dict(cls, data: Dict[str, Any]) -> IngestionConfig:
        target_threshold = float(data.get("target_threshold", 0.82))
        language = data.get("language")
        preset = str(data.get("preset", "docling_fast"))
        align_skew = bool(data.get("align_skew", True))
        visualize = bool(data.get("visualize", True))
        output_dir = str(data.get("output_dir", "output"))
        raw_scale = data.get("ocr_scale")
        ocr_scale = float(raw_scale) if raw_scale is not None else None
        force_full_page_ocr = bool(data.get("force_full_page_ocr", False))
        do_table_structure = bool(data.get("do_table_structure", True))

        return cls(
            target_threshold=target_threshold,
            language=language,
            preset=preset,
            align_skew=align_skew,
            visualize=visualize,
            output_dir=output_dir,
            ocr_scale=ocr_scale,
            force_full_page_ocr=force_full_page_ocr,
            do_table_structure=do_table_structure,
        )


@dataclass
class DocumentPlan:
    """Executable plan defining candidate preset hierarchy and quality thresholds."""
    document_path: str = ""
    criteria: PlannerCriteria = field(default_factory=PlannerCriteria)
    language: Optional[str] = None
    target_threshold: float = 0.82
    primary_preset: str = "docling_fast"
    fallback_queue: List[Dict[str, Any]] = field(default_factory=list)
    preset_order: List[str] = field(default_factory=lambda: ["docling_fast"])
    suggested_order: List[str] = field(default_factory=lambda: ["docling_fast"])
    overridden: bool = False
    scores: Dict[str, float] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.preset_order and self.primary_preset:
            self.preset_order = [self.primary_preset]
        if not self.suggested_order and self.primary_preset:
            self.suggested_order = [self.primary_preset]

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
        criteria_dict = self.criteria.to_dict()
        return {
            "document_path": self.document_path,
            "criteria": criteria_dict,
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
        output_dir: str = "output",
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

    def evolve(self, **changes: Any) -> DocumentPlan:
        """Returns a copy of the plan with specified fields updated."""
        return replace(self, **changes)

    def save(self, output_path: str = os.path.join("output", "plan.json")) -> str:
        dir_path = os.path.dirname(output_path)
        mkdirs(dir_path)
        plan_dict = self.to_dict()
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(plan_dict, f, indent=2)
        return output_path

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DocumentPlan:
        raw_criteria = data.get("criteria")
        if isinstance(raw_criteria, dict):
            criteria = PlannerCriteria.from_dict(raw_criteria)
        else:
            criteria = PlannerCriteria.from_dict(data)

        document_path = str(data.get("document_path", ""))
        language = data.get("language")
        target_threshold = float(data.get("target_threshold", 0.82))
        primary_preset = str(data.get("primary_preset", "docling_fast"))
        fallback_queue = list(data.get("fallback_queue", []))
        preset_order = list(data.get("preset_order", ["docling_fast"]))
        suggested_order = list(data.get("suggested_order", ["docling_fast"]))
        overridden = bool(data.get("overridden", False))
        scores = dict(data.get("scores", {}))
        now_iso = datetime.now(timezone.utc).isoformat()
        created_at = str(data.get("created_at", now_iso))

        return cls(
            document_path=document_path,
            criteria=criteria,
            language=language,
            target_threshold=target_threshold,
            primary_preset=primary_preset,
            fallback_queue=fallback_queue,
            preset_order=preset_order,
            suggested_order=suggested_order,
            overridden=overridden,
            scores=scores,
            created_at=created_at,
        )

    @classmethod
    def load(cls, file_path: str) -> DocumentPlan:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
