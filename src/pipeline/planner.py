"""
src/pipeline/planner.py

Data-Driven Preset Planner.
Inquires about document characteristics and system constraints, computes preset suitability
rankings, allows user override, and produces an executable execution plan.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Any

from src.pipeline.planner_models import DocumentPlan
from src.pipeline.planner_options import (
    DEFAULT_PRESET_WEIGHTS,
    TAXONOMY_OPTIONS,
    TARGET_OPTIONS,
    SECURITY_OPTIONS,
)
from src.pipeline.planner_wizard import resolve_choice, run_interactive_wizard
from src.pipeline.planner_server import serve_data_shape_wizard

__all__ = [
    "DocumentPlan",
    "PresetPlanner",
    "DEFAULT_PRESET_WEIGHTS",
    "TAXONOMY_OPTIONS",
    "TARGET_OPTIONS",
    "SECURITY_OPTIONS",
    "resolve_choice",
    "run_interactive_wizard",
    "serve_data_shape_wizard",
]


class PresetPlanner:
    """Calculates preset confidence scores and generates pipeline execution plans."""

    def __init__(self, weights: Optional[Dict[str, Dict[str, float]]] = None):
        self.weights = weights or DEFAULT_PRESET_WEIGHTS

    def calculate_scores(
        self,
        taxonomy: str,
        target: str = "high_precision_structure",
        security: str = "air_gapped_local",
        *args: Any,
        **kwargs: Any
    ) -> Dict[str, float]:
        """Calculates preset suitability scores based on document taxonomy, quality target, and security constraints."""
        # Handle backwards-compatible positional call: (taxonomy, hardware, target, security)
        if args:
            actual_target = security
            actual_security = str(args[0])
        else:
            actual_target = target
            actual_security = security

        answers = [taxonomy, actual_target, actual_security]
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
        target: str = "high_precision_structure",
        security: str = "air_gapped_local",
        language: Optional[str] = None,
        target_threshold: float = 0.82,
        override_order: Optional[List[str]] = None,
        override_primary: Optional[str] = None,
        *args: Any,
        **kwargs: Any
    ) -> DocumentPlan:
        """Constructs an executable DocumentPlan instance with fallback queues."""
        scores = self.calculate_scores(taxonomy=taxonomy, target=target, security=security)
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

    def browser_session(
        self,
        default_doc: Optional[str] = None,
        default_lang: Optional[str] = None,
        default_threshold: float = 0.82,
        output_dir: str = "output",
        port: int = 8000,
        open_browser: bool = True
    ) -> DocumentPlan:
        """Interactive in-browser data shape configuration wizard delegating to serve_data_shape_wizard."""
        return serve_data_shape_wizard(
            planner=self,
            default_doc=default_doc,
            default_lang=default_lang,
            default_threshold=default_threshold,
            output_dir=output_dir,
            port=port,
            open_browser=open_browser
        )
