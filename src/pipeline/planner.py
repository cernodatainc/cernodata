"""
src/pipeline/planner.py

Data-Driven Preset Planner.
Inquires about document characteristics and system constraints, computes preset suitability
rankings, allows user override, and produces an executable execution plan.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable

from src.pipeline.planner_models import DocumentPlan
from src.pipeline.planner_options import (
    DEFAULT_PRESET_WEIGHTS,
    TAXONOMY_OPTIONS,
    HARDWARE_OPTIONS,
    TARGET_OPTIONS,
    SECURITY_OPTIONS,
)
from src.pipeline.planner_wizard import resolve_choice, run_interactive_wizard

__all__ = [
    "DocumentPlan",
    "PresetPlanner",
    "DEFAULT_PRESET_WEIGHTS",
    "TAXONOMY_OPTIONS",
    "HARDWARE_OPTIONS",
    "TARGET_OPTIONS",
    "SECURITY_OPTIONS",
    "resolve_choice",
    "run_interactive_wizard",
]


class PresetPlanner:
    """Calculates preset confidence scores and generates pipeline execution plans."""

    def __init__(self, weights: Optional[Dict[str, Dict[str, float]]] = None):
        self.weights = weights or DEFAULT_PRESET_WEIGHTS

    def calculate_scores(self, taxonomy: str, hardware: str, target: str, security: str) -> Dict[str, float]:
        """Calculates preset suitability scores based on document and hardware parameters."""
        answers = [taxonomy, hardware, target, security]
        scores: Dict[str, float] = {}

        for preset_id, weight_map in self.weights.items():
            matched_weights = [weight_map.get(ans, 0.50) for ans in answers]
            score = sum(matched_weights) / len(matched_weights)
            scores[preset_id] = round(score, 3)

        return scores

    def suggest_preset_order(self, scores: Dict[str, float]) -> List[str]:
        """Sorts presets in descending order of calculated score."""
        return sorted(scores.keys(), key=lambda p: scores[p], reverse=True)

    def create_plan(
        self,
        document_path: str = "",
        taxonomy: str = "general_text",
        hardware: str = "low_spec_cpu",
        target: str = "high_precision_structure",
        security: str = "air_gapped_local",
        language: str = "en",
        target_threshold: float = 0.82,
        override_order: Optional[List[str]] = None,
        override_primary: Optional[str] = None
    ) -> DocumentPlan:
        """Constructs an executable DocumentPlan instance with fallback queues."""
        scores = self.calculate_scores(taxonomy, hardware, target, security)
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
        fallback_queue = [{"preset": p, "score": scores.get(p, 0.50)} for p in order[1:]]

        return DocumentPlan(
            document_path=document_path,
            taxonomy=taxonomy,
            hardware=hardware,
            target=target,
            security=security,
            language=language,
            target_threshold=target_threshold,
            primary_preset=primary_preset,
            fallback_queue=fallback_queue,
            preset_order=order,
            suggested_order=suggested,
            overridden=overridden,
            scores=scores,
            created_at=datetime.now(timezone.utc).isoformat()
        )

    @staticmethod
    def _resolve_choice(choice: str, options: List[tuple[str, str]], default: str) -> str:
        """Backwards compatible resolution helper delegating to resolve_choice."""
        return resolve_choice(choice, options, default)

    def interactive_session(
        self,
        input_func: Callable[[str], str] = input,
        print_func: Callable[..., None] = print,
        default_doc: Optional[str] = None
    ) -> DocumentPlan:
        """Interactive questionnaire wizard delegating to run_interactive_wizard."""
        return run_interactive_wizard(
            planner=self,
            input_func=input_func,
            print_func=print_func,
            default_doc=default_doc
        )
