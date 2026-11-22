"""
src/pipeline/attempt_runner.py

Execution and record structuring for individual pipeline extraction attempts.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple

from src.dom import DocumentDOM
from src.pipeline.execution_models import AttemptRecord
from src.pipeline.parsers.dispatch import parse_document
from src.pipeline.pipeline_steps import (
    align_document_skew,
    evaluate_quality_and_decision_tree,
    run_postprocessing_steps,
)
from src.pipeline.planner.models import IngestionConfig


class AttemptRunner:
    """Coordinates executing individual parsing/evaluation attempts and records history."""

    def __init__(
        self,
        parse_fn: Optional[Callable[..., DocumentDOM]] = None,
        align_fn: Optional[Callable[..., DocumentDOM]] = None,
        evaluate_fn: Optional[Callable[..., Tuple[Dict[str, Any], List[Dict[str, Any]]]]] = None,
        postprocess_fn: Optional[Callable[..., DocumentDOM]] = None,
    ) -> None:
        self._parse_fn = parse_fn or parse_document
        self._align_fn = align_fn or align_document_skew
        self._evaluate_fn = evaluate_fn or evaluate_quality_and_decision_tree
        self._postprocess_fn = postprocess_fn or run_postprocessing_steps

    def execute_attempt(
        self,
        pdf_path: str,
        config: IngestionConfig,
        curr_score: float,
        next_score: float,
        next_preset_id: Optional[str] = None,
    ) -> Tuple[DocumentDOM, Dict[str, Any], List[Dict[str, Any]]]:
        """Executes a single extraction attempt: parse -> skew align -> postprocess -> quality evaluate."""
        cached_dom_lookup = config.options.get("cached_dom_lookup")
        is_wiggled = bool(
            config.ocr_scale is not None
            or config.force_full_page_ocr
            or config.options.get("wiggle_parameters")
        )
        dom: Optional[DocumentDOM] = None
        if callable(cached_dom_lookup) and not is_wiggled:
            maybe_dom = cached_dom_lookup(config.preset)
            if isinstance(maybe_dom, DocumentDOM):
                dom = maybe_dom

        if dom is None:
            dom = self._parse_fn(pdf_path, config=config)
            dom = self._align_fn(dom, pdf_path, config.align_skew)
            dom = self._postprocess_fn(dom, config, pdf_path)

        decision, violations = self._evaluate_fn(
            dom,
            config=config,
            current_preset_score=curr_score,
            next_preset_score=next_score,
            next_preset_id=next_preset_id,
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
        resolved_action = action if action is not None else decision["decision_tree"]["action"]
        resolved_reason = reason if reason is not None else decision["decision_tree"].get("reason")
        record: AttemptRecord = {
            "step": step,
            "preset": preset,
            "overall_confidence": float(decision["overall_confidence"]),
            "per_page_confidence": decision.get("per_page_confidence"),
            "status": decision.get("status"),
            "is_accepted": bool(decision["is_accepted"]),
            "violations_count": len(violations),
            "action": resolved_action,
            "reason": resolved_reason,
        }
        if detail is not None:
            record["detail"] = detail
        if parameters is not None:
            record["parameters"] = parameters
        return record
