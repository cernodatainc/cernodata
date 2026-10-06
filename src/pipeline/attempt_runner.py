"""
src/pipeline/attempt_runner.py

Execution and record structuring for individual pipeline extraction attempts.
"""

from typing import Dict, Any, List, Tuple, Optional, Callable

from src.dom import DocumentDOM
from src.pipeline.planner_models import IngestionConfig
from src.pipeline.parser_dispatch import parse_document
from src.pipeline.pipeline_steps import align_document_skew, evaluate_quality_and_decision_tree


class AttemptRunner:
    """Coordinates executing individual parsing/evaluation attempts and records history."""

    def __init__(
        self,
        parse_fn: Optional[Callable[..., DocumentDOM]] = None,
        align_fn: Optional[Callable[..., DocumentDOM]] = None,
        evaluate_fn: Optional[Callable[..., Tuple[Dict[str, Any], List[Dict[str, Any]]]]] = None,
    ) -> None:
        self._parse_fn = parse_fn
        self._align_fn = align_fn
        self._evaluate_fn = evaluate_fn

    def execute_attempt(
        self,
        pdf_path: str,
        config: IngestionConfig,
        curr_score: float = 0.90,
        next_score: float = 0.72,
    ) -> Tuple[DocumentDOM, Dict[str, Any], List[Dict[str, Any]]]:
        """Executes a single extraction attempt: parse -> skew align -> quality evaluate."""
        parse_func = self._parse_fn or parse_document
        align_func = self._align_fn or align_document_skew
        eval_func = self._evaluate_fn or evaluate_quality_and_decision_tree

        dom = parse_func(pdf_path, config=config)
        dom = align_func(dom, pdf_path, config.align_skew)
        decision, violations = eval_func(
            dom,
            config=config,
            current_preset_score=curr_score,
            next_preset_score=next_score,
        )
        return dom, decision, violations

    @staticmethod
    def make_attempt_record(
        step: int,
        preset: str,
        decision: Dict[str, Any],
        violations: List[Dict[str, Any]],
        action: Optional[str] = None,
        reason: Optional[str] = None,
        detail: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Builds a structured attempt record for tracking iteration history."""
        record: Dict[str, Any] = {
            "step": step,
            "preset": preset,
            "overall_confidence": decision.get("overall_confidence"),
            "per_page_confidence": decision.get("per_page_confidence"),
            "status": decision.get("status"),
            "is_accepted": decision.get("is_accepted", False),
            "violations_count": len(violations),
            "action": action or decision.get("decision_tree", {}).get("action"),
            "reason": reason or decision.get("decision_tree", {}).get("reason"),
        }
        if detail is not None:
            record["detail"] = detail
        if parameters is not None:
            record["parameters"] = parameters
        return record


_default_attempt_runner = AttemptRunner()


def execute_attempt(
    pdf_path: str,
    config: IngestionConfig,
    curr_score: float = 0.90,
    next_score: float = 0.72,
) -> Tuple[DocumentDOM, Dict[str, Any], List[Dict[str, Any]]]:
    """Module-level function executing a single extraction attempt."""
    return _default_attempt_runner.execute_attempt(pdf_path, config, curr_score, next_score)


def make_attempt_record(
    step: int,
    preset: str,
    decision: Dict[str, Any],
    violations: List[Dict[str, Any]],
    action: Optional[str] = None,
    reason: Optional[str] = None,
    detail: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Module-level helper constructing structured attempt history record."""
    return AttemptRunner.make_attempt_record(
        step, preset, decision, violations, action, reason, detail, parameters
    )
