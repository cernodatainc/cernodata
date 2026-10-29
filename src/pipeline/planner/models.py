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
    """Strongly-typed criteria inputs for preset suitability ranking and verification."""
    taxonomy: str = "general_text"
    target: str = "high_precision_structure"
    security: str = "air_gapped_local"
    verification_layers: List[str] = field(
        default_factory=lambda: ["symbols", "diacritics", "structure", "tables", "geometry"]
    )
    options: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        if self.options:
            for k, v in self.options.items():
                res.setdefault(k, v)
        return res

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves an attribute or option value safely."""
        if hasattr(self, key):
            return getattr(self, key)
        return self.options.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Sets an arbitrary option or attribute value."""
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            self.options[key] = value

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PlannerCriteria:
        known = {"taxonomy", "target", "security", "verification_layers", "options"}
        taxonomy = str(data.get("taxonomy", "general_text"))
        target = str(data.get("target", "high_precision_structure"))
        security = str(data.get("security", "air_gapped_local"))
        raw_layers = data.get("verification_layers")
        if raw_layers is not None and isinstance(raw_layers, (list, tuple)):
            layers = [str(x) for x in raw_layers]
        else:
            layers = ["symbols", "diacritics", "structure", "tables", "geometry"]

        extra_opts = dict(data.get("options", {}))
        for k, v in data.items():
            if k not in known:
                extra_opts.setdefault(k, v)

        return cls(
            taxonomy=taxonomy,
            target=target,
            security=security,
            verification_layers=layers,
            options=extra_opts,
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
    verification_layers: Optional[List[str]] = None
    options: Dict[str, Any] = field(default_factory=dict)
    # TODO(stride): Extend `IngestionConfig` with optional paths/flags for `test_suite_path` (TASK-107),
    # `custom_presets_path` (TASK-204), `postprocess_steps` (TASK-506), and `template_hint_path` (TASK-903).

    def get_option(self, key: str, default: Any = None) -> Any:
        """Retrieves a configuration attribute or dynamic option value."""
        if hasattr(self, key):
            val = getattr(self, key)
            if val is not None:
                return val
        return self.options.get(key, default)

    def set_option(self, key: str, value: Any) -> None:
        """Sets a configuration attribute or dynamic option value."""
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            self.options[key] = value

    def __getitem__(self, key: str) -> Any:
        val = self.get_option(key)
        if val is None and key not in self.options and not hasattr(self, key):
            raise KeyError(key)
        return val

    def get(self, key: str, default: Any = None) -> Any:
        return self.get_option(key, default)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        if self.options:
            for k, v in self.options.items():
                res.setdefault(k, v)
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> IngestionConfig:
        known = {
            "target_threshold", "language", "preset", "align_skew", "visualize",
            "output_dir", "ocr_scale", "force_full_page_ocr", "do_table_structure",
            "verification_layers", "options",
        }
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
        raw_layers = data.get("verification_layers")
        verification_layers = [str(x) for x in raw_layers] if raw_layers is not None else None

        extra_opts = dict(data.get("options", {}))
        for k, v in data.items():
            if k not in known:
                extra_opts.setdefault(k, v)

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
            verification_layers=verification_layers,
            options=extra_opts,
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
    verification_layers: List[str] = field(
        default_factory=lambda: ["symbols", "diacritics", "structure", "tables", "geometry"]
    )
    options: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.preset_order and self.primary_preset:
            self.preset_order = [self.primary_preset]
        if not self.suggested_order and self.primary_preset:
            self.suggested_order = [self.primary_preset]

    def get_option(self, key: str, default: Any = None) -> Any:
        """Retrieves a plan attribute or dynamic option value."""
        if hasattr(self, key):
            val = getattr(self, key)
            if val is not None:
                return val
        return self.options.get(key, default)

    def set_option(self, key: str, value: Any) -> None:
        """Sets a plan attribute or dynamic option value."""
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            self.options[key] = value

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
        res = {
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
            "verification_layers": self.verification_layers,
            "options": self.options,
            "created_at": self.created_at,
        }
        if self.options:
            for k, v in self.options.items():
                res.setdefault(k, v)
        return res

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
            verification_layers=self.verification_layers,
            options=dict(self.options),
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
        raw_layers = data.get("verification_layers", criteria.verification_layers)
        verification_layers = [str(x) for x in raw_layers] if raw_layers is not None else ["symbols", "diacritics", "structure", "tables", "geometry"]
        now_iso = datetime.now(timezone.utc).isoformat()
        created_at = str(data.get("created_at", now_iso))

        known = {
            "criteria", "document_path", "language", "target_threshold", "primary_preset",
            "fallback_queue", "preset_order", "suggested_order", "overridden", "scores",
            "verification_layers", "options", "created_at", "taxonomy", "target", "security",
        }
        extra_opts = dict(data.get("options", {}))
        for k, v in data.items():
            if k not in known:
                extra_opts.setdefault(k, v)

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
            verification_layers=verification_layers,
            options=extra_opts,
            created_at=created_at,
        )

    @classmethod
    def load(cls, file_path: str) -> DocumentPlan:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
