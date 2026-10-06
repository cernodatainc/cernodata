"""
src/pipeline/attempt_runner.py

Execution and record structuring for individual pipeline extraction attempts.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple

from src.dom import DocumentDOM
from src.pipeline.execution_models import AttemptRecord
from src.pipeline.parser_dispatch import DocumentParserDispatcher, parse_document
from src.pipeline.pipeline_steps import align_document_skew, evaluate_quality_and_decision_tree
from src.pipeline.planner_models import IngestionConfig


class AttemptRunner:
    """Coordinates executing individual parsing/evaluation attempts and records history."""

    def __init__(
        self,
        parse_fn: Optional[Callable[..., DocumentDOM]] = None,
        align_fn: Optional[Callable[..., DocumentDOM]] = None,
        evaluate_fn: Optional[Callable[..., Tuple[Dict[str, Any], List[Dict[str, Any]]]]] = None,
    ) -> None:
        self._parse_fn = parse_fn or parse_document
        self._align_fn = align_fn or align_document_skew
        self._evaluate_fn = evaluate_fn or evaluate_quality_and_decision_tree

    def execute_attempt(
        self,
        pdf_path: str,
        config: IngestionConfig,
        curr_score: float = 0.90,
        next_score: float = 0.72,
    ) -> Tuple[DocumentDOM, Dict[str, Any], List[Dict[str, Any]]]:
        """Executes a single extraction attempt: parse -> skew align -> quality evaluate."""
        dom = self._parse_fn(pdf_path, config=config)
        dom = self._align_fn(dom, pdf_path, config.align_skew)
        decision, violations = self._evaluate_fn(
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
    ) -> AttemptRecord:
        """Builds a structured attempt record for tracking iteration history."""
        record: AttemptRecord = {
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
