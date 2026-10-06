"""
src/pipeline/orchestrator.py

End-to-end pipeline runner orchestrating parsing, text skew alignment, quality evaluation, exports, and rendering.
Supports executing custom and planner-generated execution plans.
"""

from typing import Dict, Any, List, Tuple, Optional, Union, Callable

from src.utils import resolve_pdf_path
from src.dom import DocumentDOM
from src.pipeline.decision_tree import DEFAULT_TARGET_CONFIDENCE_THRESHOLD
from src.pipeline.planner_models import DocumentPlan, IngestionConfig
from src.pipeline.execution_models import PipelineExecutionResult, AttemptRecord
from src.pipeline.parser_dispatch import parse_document
from src.pipeline.pipeline_steps import align_document_skew, evaluate_quality_and_decision_tree
from src.pipeline.attempt_runner import AttemptRunner, execute_attempt, make_attempt_record
from src.pipeline.fallback_handler import FallbackLoopHandler
from src.pipeline.artifact_exporter import (
    render_visual_overlays,
    export_interactive_html_viewer,
    export_pipeline_artifacts,
)

__all__ = [
    "IngestionConfig",
    "PipelineExecutionResult",
    "AttemptRecord",
    "parse_document",
    "align_document_skew",
    "evaluate_quality_and_decision_tree",
    "render_visual_overlays",
    "export_interactive_html_viewer",
    "export_pipeline_artifacts",
    "execute_pipeline",
    "run_pipeline",
    "PipelineOrchestrator",
]


def _execute_attempt(
    pdf_path: str,
    config: IngestionConfig,
    curr_score: float = 0.90,
    next_score: float = 0.72,
) -> Tuple[DocumentDOM, Dict[str, Any], List[Dict[str, Any]]]:
    """Executes a single extraction attempt: parse -> skew align -> quality evaluate."""
    dom = parse_document(pdf_path, config=config)
    dom = align_document_skew(dom, pdf_path, config.align_skew)
    decision, violations = evaluate_quality_and_decision_tree(
        dom,
        config=config,
        current_preset_score=curr_score,
        next_preset_score=next_score,
    )
    return dom, decision, violations


def _make_attempt_record(
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
    return make_attempt_record(
        step=step,
        preset=preset,
        decision=decision,
        violations=violations,
        action=action,
        reason=reason,
        detail=detail,
        parameters=parameters,
    )


class PipelineOrchestrator:
    """Coordinates end-to-end document extraction, fallback loops, and artifact generation."""

    def __init__(
        self,
        fallback_handler: Optional[FallbackLoopHandler] = None,
    ) -> None:
        self.fallback_handler = fallback_handler or FallbackLoopHandler()

    def execute(
        self,
        pdf_path: str,
        config: IngestionConfig,
        plan: Optional[DocumentPlan] = None,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> PipelineExecutionResult:
        """Executes end-to-end extraction pipeline with concrete configuration and optional fallback orchestration."""
        def notify(pct: int, step_desc: str, log_msg: str) -> None:
            if progress_callback is not None:
                try:
                    progress_callback(pct, step_desc, log_msg)
                except Exception:
                    pass

        plan_obj = plan
        resolved_path = resolve_pdf_path(pdf_path)
        notify(20, "Step 1: Document Validation & Subdivision", f"Ingestion initiated for '{resolved_path}' (Preset: {config.preset}, Lang: {config.language}).")

        pdf_path = resolved_path
        attempts: List[Dict[str, Any]] = []

        next_candidate, part_of_plan, curr_score, next_score = self.fallback_handler.resolve_candidate_scores(
            config=config,
            plan=plan_obj,
        )

        # Step 1: Initial Parse with Primary Preset
        notify(40, f"Step 2: Executing Preset '{config.preset}'", f"Running extraction with preset '{config.preset}'...")
        dom, decision, violations = _execute_attempt(
            pdf_path, config, curr_score, next_score
        )
        attempts.append(_make_attempt_record(1, config.preset, decision, violations))
        notify(65, "Step 3: Document Skew Alignment & Verification", "Document parsed. Analyzing layout geometry and quality rules...")

        # Step 2: Fallback loop handling (Path A or Path B)
        dom, decision, violations = self.fallback_handler.handle_fallback(
            pdf_path=pdf_path,
            config=config,
            dom=dom,
            decision=decision,
            violations=violations,
            attempts=attempts,
            next_candidate=next_candidate,
            part_of_plan=part_of_plan,
            curr_score=curr_score,
            next_score=next_score,
            execute_attempt_fn=_execute_attempt,
            make_attempt_record_fn=_make_attempt_record,
            notify_fn=notify,
        )

        decision["attempts"] = attempts

        plan_dict = plan_obj.to_dict() if plan_obj else None
        notify(88, "Step 5: Exporting Artifacts & Overlays", "Saving DocumentDOM, quality violations, and rendering visual overlays...")
        rendered_images = render_visual_overlays(pdf_path, dom, violations, config.visualize, config.output_dir, decision=decision)
        dom_json_path, violations_json_path, plan_result_path = export_pipeline_artifacts(
            dom, decision, violations, config.language, config.output_dir, plan=plan_dict
        )
        html_viewer_path = export_interactive_html_viewer(pdf_path, dom, decision, violations, config.output_dir, plan=plan_dict)

        status_str = str(decision.get("status", "ACCEPT"))
        score_val = float(decision.get("overall_confidence", 1.0) or 1.0)
        notify(100, f"Step 5: Decision Tree Complete ({status_str})", f"Run complete: Status '{status_str}', Confidence: {score_val:.4f}, Violations: {len(violations)}.")

        return {
            "dom": dom.to_dict(),
            "decision": decision,
            "violations": violations,
            "dom_json_path": dom_json_path,
            "violations_json_path": violations_json_path,
            "plan_result_path": plan_result_path,
            "html_viewer_path": html_viewer_path,
            "rendered_images": rendered_images,
            "plan": plan_dict,
        }


_default_orchestrator = PipelineOrchestrator()


def execute_pipeline(
    pdf_path: str,
    config: IngestionConfig,
    plan: Optional[DocumentPlan] = None,
    progress_callback: Optional[Callable[[int, str, str], None]] = None,
) -> PipelineExecutionResult:
    """Executes end-to-end extraction pipeline with concrete configuration and optional fallback orchestration."""
    return _default_orchestrator.execute(
        pdf_path=pdf_path,
        config=config,
        plan=plan,
        progress_callback=progress_callback,
    )


def run_pipeline(
    pdf_path: Optional[str] = None,
    target_threshold: float = DEFAULT_TARGET_CONFIDENCE_THRESHOLD,
    language: Optional[str] = "en",
    preset: str = "docling_fast",
    align_skew: bool = True,
    visualize: bool = True,
    output_dir: str = "output",
    plan: Optional[Union[str, Dict[str, Any], DocumentPlan]] = None,
    config: Optional[IngestionConfig] = None,
    progress_callback: Optional[Callable[[int, str, str], None]] = None,
) -> PipelineExecutionResult:
    """Convenience facade: resolves flexible ingress arguments into strongly-typed execution inputs."""
    plan_obj: Optional[DocumentPlan] = None
    if plan:
        if isinstance(plan, str):
            plan_obj = DocumentPlan.load(plan)
        elif isinstance(plan, dict):
            plan_obj = DocumentPlan.from_dict(plan)
        elif isinstance(plan, DocumentPlan):
            plan_obj = plan

    if config is not None:
        cfg = config
    elif plan_obj is not None:
        cfg = plan_obj.to_ingestion_config(
            align_skew=align_skew,
            visualize=visualize,
            output_dir=output_dir,
        )
    else:
        cfg = IngestionConfig(
            target_threshold=target_threshold,
            language=language,
            preset=preset,
            align_skew=align_skew,
            visualize=visualize,
            output_dir=output_dir,
        )

    resolved_path = pdf_path or (plan_obj.document_path if plan_obj else None)
    if not resolved_path:
        raise ValueError("Input document path is required.")

    return execute_pipeline(
        pdf_path=resolved_path,
        config=cfg,
        plan=plan_obj,
        progress_callback=progress_callback,
    )
