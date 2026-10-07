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
        self.weights = weights or DEFAULT_PRESET_WEIGHTS

    def calculate_scores(
        self,
        criteria: Optional[Union[PlannerCriteria, str]] = None,
        taxonomy: Optional[str] = None,
        target: str = "high_precision_structure",
        security: str = "air_gapped_local",
        *args: Any,
        **kwargs: Any,
    ) -> Dict[str, float]:
        """Calculates preset suitability scores based on strongly-typed PlannerCriteria or backward-compatible arguments."""
        if isinstance(criteria, PlannerCriteria):
            resolved_criteria = criteria
        elif isinstance(taxonomy, PlannerCriteria):
            resolved_criteria = taxonomy
        else:
            tax = str(criteria if isinstance(criteria, str) else (taxonomy or "general_text"))
            # Handle backwards-compatible positional call: (taxonomy, hardware, target, security)
            if args:
                actual_target = security
                actual_security = str(args[0])
            else:
                actual_target = target
                actual_security = security

            resolved_criteria = PlannerCriteria(
                taxonomy=tax,
                target=actual_target,
                security=actual_security,
            )

        scores: Dict[str, float] = {}
        for preset_id, weight_map in self.weights.items():
            matched_weights = [weight_map.get(ans, 0.50) for ans in resolved_criteria.values()]
            score = sum(matched_weights) / len(matched_weights)
            scores[preset_id] = round(score, 3)

        return scores

    def suggest_preset_order(self, scores: Dict[str, float]) -> List[str]:
        """Sorts presets in descending order of calculated score."""
        return sorted(scores.keys(), key=lambda p: scores[p], reverse=True)

    def create_plan(
        self,
        document_path: str = "",
        criteria: Optional[Union[PlannerCriteria, str]] = None,
        taxonomy: Optional[str] = None,
        target: str = "high_precision_structure",
        security: str = "air_gapped_local",
        language: Optional[str] = None,
        target_threshold: float = 0.82,
        override_order: Optional[List[str]] = None,
        override_primary: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ) -> DocumentPlan:
        """Constructs an executable DocumentPlan instance using strongly-typed PlannerCriteria."""
        if isinstance(criteria, PlannerCriteria):
            resolved_criteria = criteria
        elif isinstance(taxonomy, PlannerCriteria):
            resolved_criteria = taxonomy
        else:
            tax = str(criteria if isinstance(criteria, str) else (taxonomy or "general_text"))
            resolved_criteria = PlannerCriteria(
                taxonomy=tax,
                target=target,
                security=security,
            )

        scores = self.calculate_scores(criteria=resolved_criteria)
        suggested = self.suggest_preset_order(scores)

        overridden = False
        if override_order:
            order = list(override_order)
            overridden = (order != suggested)
        elif override_primary:
            order = [override_primary] + [p for p in suggested if p != override_primary]
            overridden = (order != suggested)
        else:
            order = list(suggested)

        primary_preset = order[0]
        fallback_queue: List[Dict[str, Any]] = []
        for p in order[1:]:
            p_score = scores.get(p, 0.50)
            fallback_queue.append({"preset": p, "score": p_score})

        created_at_iso = datetime.now(timezone.utc).isoformat()
        return DocumentPlan(
            document_path=document_path,
            criteria=resolved_criteria,
            language=language,
            target_threshold=target_threshold,
            primary_preset=primary_preset,
            fallback_queue=fallback_queue,
            preset_order=order,
            suggested_order=suggested,
            overridden=overridden,
            scores=scores,
            created_at=created_at_iso,
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
        """Interactive in-browser data shape configuration wizard delegating to serve_data_shape_wizard."""
        from src.pipeline.planner.server import serve_data_shape_wizard
        return serve_data_shape_wizard(
            planner=self,
            default_doc=default_doc,
            default_lang=default_lang,
            default_threshold=default_threshold,
            output_dir=output_dir,
            port=port,
            open_browser=open_browser,
        )
