"""
src/pipeline/planner/models.py

Execution plan data model and serialization routines.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Set

from src.utils import mkdirs

DEFAULT_PLANNER_LAYERS: List[str] = ["symbols", "diacritics", "structure", "tables", "geometry"]


class ExtensibleOptionsMixin:
    """Shared mixin for dataclasses supporting dynamic key-value options alongside typed fields."""

    options: Dict[str, Any]

    def get_option(self, key: str, default: Any = None) -> Any:
        """Retrieves a typed attribute or dynamic option value."""
        if hasattr(self, key):
            val = getattr(self, key)
            if val is not None:
                return val
        return self.options.get(key, default)

    def set_option(self, key: str, value: Any) -> None:
        """Sets a typed attribute or dynamic option value."""
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            self.options[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves an attribute or option value safely."""
        return self.get_option(key, default)

    def set(self, key: str, value: Any) -> None:
        """Sets an arbitrary option or attribute value."""
        self.set_option(key, value)

    def __getitem__(self, key: str) -> Any:
        val = self.get_option(key)
        if val is None and key not in self.options and not hasattr(self, key):
            raise KeyError(key)
        return val

    def _merge_options(self, base: Dict[str, Any]) -> Dict[str, Any]:
        if self.options:
            for k, v in self.options.items():
                base.setdefault(k, v)
        return base

    @staticmethod
    def _extract_extra_options(data: Mapping[str, Any], known: Set[str]) -> Dict[str, Any]:
        extra_opts = dict(data.get("options", {}))
        for k, v in data.items():
            if k not in known:
                extra_opts.setdefault(k, v)
        return extra_opts


@dataclass
class PlannerCriteria(ExtensibleOptionsMixin):
    """Strongly-typed criteria inputs for preset suitability ranking and verification."""
    taxonomy: str = "general_text"
    target: str = "high_precision_structure"
    security: str = "air_gapped_local"
    verification_layers: List[str] = field(default_factory=lambda: list(DEFAULT_PLANNER_LAYERS))
    options: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return self._merge_options(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PlannerCriteria:
        known = {"taxonomy", "target", "security", "verification_layers", "options"}
        raw_layers = data.get("verification_layers")
        layers = (
            [str(x) for x in raw_layers]
            if isinstance(raw_layers, (list, tuple))
            else list(DEFAULT_PLANNER_LAYERS)
        )
        return cls(
            taxonomy=str(data.get("taxonomy", "general_text")),
            target=str(data.get("target", "high_precision_structure")),
            security=str(data.get("security", "air_gapped_local")),
            verification_layers=layers,
            options=cls._extract_extra_options(data, known),
        )

    def values(self) -> List[str]:
        """Returns the list of criteria values for weight matching."""
        return [self.taxonomy, self.target, self.security]


@dataclass
class IngestionConfig(ExtensibleOptionsMixin):
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

    def to_dict(self) -> Dict[str, Any]:
        return self._merge_options(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> IngestionConfig:
        known = {
            "target_threshold", "language", "preset", "align_skew", "visualize",
            "output_dir", "ocr_scale", "force_full_page_ocr", "do_table_structure",
            "verification_layers", "options",
        }
        raw_scale = data.get("ocr_scale")
        raw_layers = data.get("verification_layers")
        return cls(
            target_threshold=float(data.get("target_threshold", 0.82)),
            language=data.get("language"),
            preset=str(data.get("preset", "docling_fast")),
            align_skew=bool(data.get("align_skew", True)),
            visualize=bool(data.get("visualize", True)),
            output_dir=str(data.get("output_dir", "output")),
            ocr_scale=float(raw_scale) if raw_scale is not None else None,
            force_full_page_ocr=bool(data.get("force_full_page_ocr", False)),
            do_table_structure=bool(data.get("do_table_structure", True)),
            verification_layers=[str(x) for x in raw_layers] if raw_layers is not None else None,
            options=cls._extract_extra_options(data, known),
        )


@dataclass
class DocumentPlan(ExtensibleOptionsMixin):
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
    verification_layers: List[str] = field(default_factory=lambda: list(DEFAULT_PLANNER_LAYERS))
    options: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.preset_order and self.primary_preset:
            self.preset_order = [self.primary_preset]
        if not self.suggested_order and self.primary_preset:
            self.suggested_order = [self.primary_preset]

    def apply_preset_override(self, preset: str) -> None:
        """Applies a primary preset override and updates preset_order accordingly."""
        if preset:
            self.primary_preset = preset
            self.overridden = True
            self.preset_order = [preset] + [p for p in self.preset_order if p != preset]

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
        res = {
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
            "verification_layers": self.verification_layers,
            "options": self.options,
            "created_at": self.created_at,
        }
        return self._merge_options(res)

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
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        return output_path

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DocumentPlan:
        raw_criteria = data.get("criteria")
        criteria = PlannerCriteria.from_dict(raw_criteria if isinstance(raw_criteria, dict) else data)
        raw_layers = data.get("verification_layers", criteria.verification_layers)
        verification_layers = (
            [str(x) for x in raw_layers] if raw_layers is not None else list(DEFAULT_PLANNER_LAYERS)
        )
        known = {
            "criteria", "document_path", "language", "target_threshold", "primary_preset",
            "fallback_queue", "preset_order", "suggested_order", "overridden", "scores",
            "verification_layers", "options", "created_at", "taxonomy", "target", "security",
        }
        return cls(
            document_path=str(data.get("document_path", "")),
            criteria=criteria,
            language=data.get("language"),
            target_threshold=float(data.get("target_threshold", 0.82)),
            primary_preset=str(data.get("primary_preset", "docling_fast")),
            fallback_queue=list(data.get("fallback_queue", [])),
            preset_order=list(data.get("preset_order", ["docling_fast"])),
            suggested_order=list(data.get("suggested_order", ["docling_fast"])),
            overridden=bool(data.get("overridden", False)),
            scores=dict(data.get("scores", {})),
            verification_layers=verification_layers,
            options=cls._extract_extra_options(data, known),
            created_at=str(data.get("created_at", datetime.now(timezone.utc).isoformat())),
        )

    @classmethod
    def load(cls, file_path: str) -> DocumentPlan:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
