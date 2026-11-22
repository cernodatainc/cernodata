"""
src/pipeline/planner/planner.py

Data-Driven Preset Planner.
Inquires about document characteristics and system constraints, computes preset suitability
rankings, allows user override, and produces an executable execution plan.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Union

from src.pipeline.planner.models import DocumentPlan, PlannerCriteria
from src.pipeline.planner.options import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PORT,
    DEFAULT_PRESET_WEIGHTS,
    DEFAULT_SECURITY,
    DEFAULT_SUITABILITY_SCORE,
    DEFAULT_TARGET,
    DEFAULT_TARGET_THRESHOLD,
    DEFAULT_TAXONOMY,
)
from src.pipeline.planner.wizard import resolve_choice, run_interactive_wizard


from typing import Mapping, Sequence

from src.schemas.custom_preset import (
    CustomPresetConfig,
    PresetBackendType,
    load_custom_presets_file,
)


class PresetPlanner:
    """Calculates preset confidence scores and generates pipeline execution plans."""

    _TAXONOMY_KEYS = (
        "financial_report",
        "multicolumn_article",
        "scanned_form",
        "tabular_ledger",
        "mixed_text_image",
        "general_text",
    )

    @staticmethod
    def derive_custom_preset_weights(config: CustomPresetConfig) -> Dict[str, float]:
        """Derives planner dimension suitability weights for a custom preset config."""
        hints = {str(h).strip().lower() for h in config.taxonomy_hints if str(h).strip()}
        weights: Dict[str, float] = {}
        for tax in PresetPlanner._TAXONOMY_KEYS:
            if hints:
                weights[tax] = 0.88 if tax in hints else (0.55 if tax == "general_text" else 0.45)
            else:
                weights[tax] = 0.7 if tax == "general_text" else 0.55

        for hint in hints:
            weights.setdefault(hint, 0.88)

        hw = config.hardware_weight
        if hw == "heavy_cpu":
            weights["rapid_approximate"] = 0.5
            weights["high_precision_structure"] = 0.82
        elif hw == "gpu_vram":
            weights["rapid_approximate"] = 0.45
            weights["high_precision_structure"] = 0.9
        elif hw == "light_cpu":
            weights["rapid_approximate"] = 0.85
            weights["high_precision_structure"] = 0.6
        else:
            raise ValueError(f"Unsupported hardware_weight: {hw!r}")

        if config.backend_type == PresetBackendType.HTTP_ENDPOINT:
            weights["air_gapped_local"] = 0.25
            weights["hosted_vision_api"] = 0.85
        else:
            weights["air_gapped_local"] = 0.9
            weights["hosted_vision_api"] = 0.5

        for key, val in config.suitability_weights.items():
            weights[str(key)] = float(val)
        return weights

    def __init__(
        self,
        weights: Optional[Dict[str, Dict[str, float]]] = None,
        custom_presets: Optional[Sequence[Union[CustomPresetConfig, Mapping[str, Any]]]] = None,
        custom_presets_path: Optional[str] = None,
    ) -> None:
        base_weights = weights if weights is not None else DEFAULT_PRESET_WEIGHTS
        self.weights: Dict[str, Dict[str, float]] = {
            preset_id: dict(dim_weights)
            for preset_id, dim_weights in base_weights.items()
        }
        if custom_presets_path:
            for cfg in load_custom_presets_file(custom_presets_path):
                self.register_custom_preset(cfg)
        if custom_presets:
            for item in custom_presets:
                self.register_custom_preset(item)

    def register_custom_preset(
        self,
        config: Union[CustomPresetConfig, Mapping[str, Any]],
    ) -> Dict[str, float]:
        """Merges a CustomPresetConfig's derived and explicit suitability weights into self.weights."""
        cfg = config if isinstance(config, CustomPresetConfig) else CustomPresetConfig.from_dict(config)
        merged = self.derive_custom_preset_weights(cfg)
        self.weights[cfg.preset_id] = merged
        return merged

    def _apply_hardware_calibration(self, scores: Dict[str, float]) -> Dict[str, float]:
        """No-op hook for adjusting preset scores using empirical hardware benchmark logs."""
        # TODO(TASK-1004): Calibrate preset speed/suitability weights using empirical hardware timing logs.
        return scores

    @staticmethod
    def _resolve_criteria(
        criteria: Optional[Union[PlannerCriteria, str]] = None,
        taxonomy: Optional[Union[PlannerCriteria, str]] = None,
        target: str = DEFAULT_TARGET,
        security: str = DEFAULT_SECURITY,
        verification_layers: Optional[List[str]] = None,
    ) -> PlannerCriteria:
        if isinstance(criteria, PlannerCriteria):
            resolved = criteria
        elif isinstance(taxonomy, PlannerCriteria):
            resolved = taxonomy
        else:
            tax = str(criteria if isinstance(criteria, str) else (taxonomy or DEFAULT_TAXONOMY))
            resolved = PlannerCriteria(taxonomy=tax, target=target, security=security)
        if verification_layers is not None:
            resolved.verification_layers = list(verification_layers)
        return resolved

    def calculate_scores(
        self,
        criteria: Optional[Union[PlannerCriteria, str]] = None,
        taxonomy: Optional[Union[PlannerCriteria, str]] = None,
        target: str = DEFAULT_TARGET,
        security: str = DEFAULT_SECURITY,
    ) -> Dict[str, float]:
        """Calculates preset suitability scores based on strongly-typed PlannerCriteria or dimension arguments."""
        resolved_criteria = self._resolve_criteria(criteria, taxonomy, target, security)
        scores: Dict[str, float] = {}
        for preset_id, weight_map in self.weights.items():
            matched_weights = [weight_map.get(ans, DEFAULT_SUITABILITY_SCORE) for ans in resolved_criteria.values()]
            scores[preset_id] = round(sum(matched_weights) / len(matched_weights), 3) if matched_weights else DEFAULT_SUITABILITY_SCORE

        return self._apply_hardware_calibration(scores)

    def suggest_preset_order(self, scores: Dict[str, float]) -> List[str]:
        """Sorts presets in descending order of calculated score."""
        return sorted(scores.keys(), key=lambda p: scores.get(p, 0.0), reverse=True)

    def create_plan(
        self,
        document_path: str = "",
        criteria: Optional[Union[PlannerCriteria, str]] = None,
        taxonomy: Optional[Union[PlannerCriteria, str]] = None,
        target: str = DEFAULT_TARGET,
        security: str = DEFAULT_SECURITY,
        language: Optional[str] = None,
        target_threshold: float = DEFAULT_TARGET_THRESHOLD,
        override_order: Optional[List[str]] = None,
        override_primary: Optional[str] = None,
        verification_layers: Optional[List[str]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> DocumentPlan:
        """Constructs an executable DocumentPlan instance using strongly-typed PlannerCriteria."""
        resolved_criteria = self._resolve_criteria(criteria, taxonomy, target, security, verification_layers)
        scores = self.calculate_scores(criteria=resolved_criteria)
        suggested = self.suggest_preset_order(scores)

        if override_order:
            order = list(override_order)
        elif override_primary:
            order = [override_primary] + [p for p in suggested if p != override_primary]
        else:
            order = list(suggested)
        overridden = bool(override_order or override_primary) and (order != suggested)
        fallback_queue = [{"preset": p, "score": scores.get(p, DEFAULT_SUITABILITY_SCORE)} for p in order[1:]]

        return DocumentPlan(
            document_path=document_path,
            criteria=resolved_criteria,
            language=language,
            target_threshold=target_threshold,
            primary_preset=order[0],
            fallback_queue=fallback_queue,
            preset_order=order,
            suggested_order=suggested,
            overridden=overridden,
            scores=scores,
            verification_layers=resolved_criteria.verification_layers,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _resolve_choice(choice: str, options: List[tuple[str, str]], default: str) -> str:
        """Backwards compatible resolution helper delegating to resolve_choice."""
        return resolve_choice(choice, options, default)

    def interactive_session(
        self,
        input_func: Callable[[str], str] = input,
        print_func: Callable[..., None] = print,
        default_doc: Optional[str] = None,
    ) -> DocumentPlan:
        """Interactive questionnaire wizard delegating to run_interactive_wizard."""
        return run_interactive_wizard(
            planner=self,
            input_func=input_func,
            print_func=print_func,
            default_doc=default_doc,
        )

    def browser_session(
        self,
        default_doc: Optional[str] = None,
        default_lang: Optional[str] = None,
        default_threshold: float = DEFAULT_TARGET_THRESHOLD,
        output_dir: str = DEFAULT_OUTPUT_DIR,
        port: int = DEFAULT_PORT,
        open_browser: bool = True,
    ) -> DocumentPlan:
        """Interactive in-browser data shape configuration wizard delegating to server launcher."""
        import importlib
        server_launcher = importlib.import_module("src.pipeline.server.launcher")
        return server_launcher.serve_data_shape_wizard(
            planner=self,
            default_doc=default_doc,
            default_lang=default_lang,
            default_threshold=default_threshold,
            output_dir=output_dir,
            port=port,
            open_browser=open_browser,
        )
