"""
src/pipeline/planner/models.py

Execution plan data model and serialization routines.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Set, cast

from src.pipeline.planner.options import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PRIMARY_PRESET,
    DEFAULT_SECURITY,
    DEFAULT_SUITABILITY_SCORE,
    DEFAULT_TARGET,
    DEFAULT_TARGET_THRESHOLD,
    DEFAULT_TAXONOMY,
)
from src.utils import save_json

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

    get = get_option
    set = set_option

    def __getitem__(self, key: str) -> Any:
        val = self.get_option(key)
        if val is None and key not in self.options and not hasattr(self, key):
            raise KeyError(key)
        return val

    def to_dict(self) -> Dict[str, Any]:
        """Serializes dataclass fields to dictionary merged with dynamic options."""
        return self._merge_options(asdict(cast(Any, self)))

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

    @classmethod
    def _extract_unknown_options(
        cls, data: Mapping[str, Any], extra_known: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """Extracts dynamic options not declared as dataclass fields or known aliases."""
        known = {f.name for f in fields(cast(Any, cls))}
        if extra_known:
            known.update(extra_known)
        return cls._extract_extra_options(data, known)


@dataclass
class PlannerCriteria(ExtensibleOptionsMixin):
    """Strongly-typed criteria inputs for preset suitability ranking and verification."""
    taxonomy: str = DEFAULT_TAXONOMY
    target: str = DEFAULT_TARGET
    security: str = DEFAULT_SECURITY
    verification_layers: List[str] = field(default_factory=lambda: list(DEFAULT_PLANNER_LAYERS))
    options: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PlannerCriteria:
        raw_layers = data.get("verification_layers")
        layers = (
            [str(x) for x in raw_layers]
            if isinstance(raw_layers, (list, tuple))
            else list(DEFAULT_PLANNER_LAYERS)
        )
        return cls(
            taxonomy=str(data.get("taxonomy", DEFAULT_TAXONOMY)),
            target=str(data.get("target", DEFAULT_TARGET)),
            security=str(data.get("security", DEFAULT_SECURITY)),
            verification_layers=layers,
            options=cls._extract_unknown_options(data),
        )

    def values(self) -> List[str]:
        """Returns the list of criteria values for weight matching."""
        return [self.taxonomy, self.target, self.security]


@dataclass
class IngestionConfig(ExtensibleOptionsMixin):
    """Strongly-typed pipeline configuration for document parsing and quality evaluation."""
    target_threshold: float = DEFAULT_TARGET_THRESHOLD
    language: Optional[str] = "en"
    preset: str = DEFAULT_PRIMARY_PRESET
    align_skew: bool = True
    visualize: bool = True
    output_dir: str = DEFAULT_OUTPUT_DIR
    ocr_scale: Optional[float] = None
    force_full_page_ocr: bool = False
    do_table_structure: bool = True
    verification_layers: Optional[List[str]] = None
    options: Dict[str, Any] = field(default_factory=dict)
    # TODO(stride): Extend `IngestionConfig` with optional paths/flags for `test_suite_path` (TASK-107),
    # `custom_presets_path` (TASK-204), `postprocess_steps` (TASK-506), and `template_hint_path` (TASK-903).

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> IngestionConfig:
        raw_scale = data.get("ocr_scale")
        raw_layers = data.get("verification_layers")
        return cls(
            target_threshold=float(data.get("target_threshold", DEFAULT_TARGET_THRESHOLD)),
            language=data.get("language"),
            preset=str(data.get("preset", DEFAULT_PRIMARY_PRESET)),
            align_skew=bool(data.get("align_skew", True)),
            visualize=bool(data.get("visualize", True)),
            output_dir=str(data.get("output_dir", DEFAULT_OUTPUT_DIR)),
            ocr_scale=float(raw_scale) if raw_scale is not None else None,
            force_full_page_ocr=bool(data.get("force_full_page_ocr", False)),
            do_table_structure=bool(data.get("do_table_structure", True)),
            verification_layers=[str(x) for x in raw_layers] if raw_layers is not None else None,
            options=cls._extract_unknown_options(data),
        )


@dataclass
class DocumentPlan(ExtensibleOptionsMixin):
    """Executable plan defining candidate preset hierarchy and quality thresholds."""
    document_path: str = ""
    criteria: PlannerCriteria = field(default_factory=PlannerCriteria)
    language: Optional[str] = None
    target_threshold: float = DEFAULT_TARGET_THRESHOLD
    primary_preset: str = DEFAULT_PRIMARY_PRESET
    fallback_queue: List[Dict[str, Any]] = field(default_factory=list)
    preset_order: List[str] = field(default_factory=lambda: [DEFAULT_PRIMARY_PRESET])
    suggested_order: List[str] = field(default_factory=lambda: [DEFAULT_PRIMARY_PRESET])
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
        """Applies a primary preset override and updates preset_order and fallback_queue accordingly."""
        if preset:
            self.primary_preset = preset
            self.overridden = True
            self.preset_order = [preset] + [p for p in self.preset_order if p != preset]
            self.fallback_queue = [
                {"preset": p, "score": self.scores.get(p, DEFAULT_SUITABILITY_SCORE)}
                for p in self.preset_order[1:]
            ]

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
        res = asdict(self)
        res.update({
            "criteria": self.criteria.to_dict(),
            "taxonomy": self.taxonomy,
            "target": self.target,
            "security": self.security,
        })
        return self._merge_options(res)

    def to_ingestion_config(
        self,
        align_skew: bool = True,
        visualize: bool = True,
        output_dir: str = DEFAULT_OUTPUT_DIR,
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

    def save(self, output_path: str = os.path.join(DEFAULT_OUTPUT_DIR, "plan.json")) -> str:
        return save_json(output_path, self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DocumentPlan:
        raw_criteria = data.get("criteria")
        criteria = PlannerCriteria.from_dict(raw_criteria if isinstance(raw_criteria, dict) else data)
        raw_layers = data.get("verification_layers", criteria.verification_layers)
        verification_layers = (
            [str(x) for x in raw_layers] if raw_layers is not None else list(DEFAULT_PLANNER_LAYERS)
        )
        return cls(
            document_path=str(data.get("document_path", "")),
            criteria=criteria,
            language=data.get("language"),
            target_threshold=float(data.get("target_threshold", DEFAULT_TARGET_THRESHOLD)),
            primary_preset=str(data.get("primary_preset", DEFAULT_PRIMARY_PRESET)),
            fallback_queue=list(data.get("fallback_queue", [])),
            preset_order=list(data.get("preset_order", [DEFAULT_PRIMARY_PRESET])),
            suggested_order=list(data.get("suggested_order", [DEFAULT_PRIMARY_PRESET])),
            overridden=bool(data.get("overridden", False)),
            scores=dict(data.get("scores", {})),
            verification_layers=verification_layers,
            options=cls._extract_unknown_options(data, extra_known={"taxonomy", "target", "security"}),
            created_at=str(data.get("created_at", datetime.now(timezone.utc).isoformat())),
        )

    @classmethod
    def load(cls, file_path: str) -> DocumentPlan:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
