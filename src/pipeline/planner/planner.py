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
from src.pipeline.planner.options import DEFAULT_PRESET_WEIGHTS
from src.pipeline.planner.wizard import resolve_choice, run_interactive_wizard


class PresetPlanner:
    """Calculates preset confidence scores and generates pipeline execution plans."""

    def __init__(self, weights: Optional[Dict[str, Dict[str, float]]] = None) -> None:
        # TODO(TASK-205): Merge user-defined `CustomPresetConfig` suitability weights into `self.weights`.
        self.weights = weights or DEFAULT_PRESET_WEIGHTS

    def _apply_hardware_calibration(self, scores: Dict[str, float]) -> Dict[str, float]:
        """No-op hook for adjusting preset scores using empirical hardware benchmark logs."""
        # TODO(TASK-1004): Calibrate preset speed/suitability weights using empirical hardware timing logs.
        return scores

    @staticmethod
    def _resolve_criteria(
        criteria: Optional[Union[PlannerCriteria, str]] = None,
        taxonomy: Optional[Union[PlannerCriteria, str]] = None,
        target: str = "high_precision_structure",
        security: str = "air_gapped_local",
        verification_layers: Optional[List[str]] = None,
    ) -> PlannerCriteria:
        if isinstance(criteria, PlannerCriteria):
            resolved = criteria
        elif isinstance(taxonomy, PlannerCriteria):
            resolved = taxonomy
        else:
            tax = str(criteria if isinstance(criteria, str) else (taxonomy or "general_text"))
            resolved = PlannerCriteria(taxonomy=tax, target=target, security=security)
        if verification_layers is not None:
            resolved.verification_layers = list(verification_layers)
        return resolved

    def calculate_scores(
        self,
        criteria: Optional[Union[PlannerCriteria, str]] = None,
        taxonomy: Optional[Union[PlannerCriteria, str]] = None,
        target: str = "high_precision_structure",
        security: str = "air_gapped_local",
    ) -> Dict[str, float]:
        """Calculates preset suitability scores based on strongly-typed PlannerCriteria or dimension arguments."""
        resolved_criteria = self._resolve_criteria(criteria, taxonomy, target, security)
        scores: Dict[str, float] = {}
        for preset_id, weight_map in self.weights.items():
            matched_weights = [weight_map.get(ans, 0.50) for ans in resolved_criteria.values()]
            scores[preset_id] = round(sum(matched_weights) / len(matched_weights), 3) if matched_weights else 0.50

        return self._apply_hardware_calibration(scores)

    def suggest_preset_order(self, scores: Dict[str, float]) -> List[str]:
        """Sorts presets in descending order of calculated score."""
        return sorted(scores.keys(), key=lambda p: scores.get(p, 0.0), reverse=True)

    def create_plan(
        self,
        document_path: str = "",
        criteria: Optional[Union[PlannerCriteria, str]] = None,
        taxonomy: Optional[Union[PlannerCriteria, str]] = None,
        target: str = "high_precision_structure",
        security: str = "air_gapped_local",
        language: Optional[str] = None,
        target_threshold: float = 0.82,
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
        fallback_queue = [{"preset": p, "score": scores.get(p, 0.50)} for p in order[1:]]

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
        default_threshold: float = 0.82,
        output_dir: str = "output",
        port: int = 8000,
        open_browser: bool = True,
    ) -> DocumentPlan:
        """Interactive in-browser data shape configuration wizard delegating to server launcher."""
        import importlib
        server_launcher = importlib.import_module("src.pipeline.server.launcher")
        runner = getattr(server_launcher, "serve_data_shape_wizard")
        return runner(
            planner=self,
            default_doc=default_doc,
            default_lang=default_lang,
            default_threshold=default_threshold,
            output_dir=output_dir,
            port=port,
            open_browser=open_browser,
        )
