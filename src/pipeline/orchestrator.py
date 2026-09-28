"""
src/pipeline/orchestrator.py

End-to-end pipeline runner orchestrating parsing, text skew alignment, quality evaluation, exports, and rendering.
Supports executing custom and planner-generated execution plans.
"""

import os
from dataclasses import replace
from typing import Dict, Any, List, Tuple, Optional, Union, TypedDict

from src.utils import resolve_pdf_path
from src.dom import DocumentDOM
from src.parsers import DoclingParser, PyPdfiumParser
from src.quality import detect_quality_violations, apply_text_skew_alignment
from src.pipeline.decision_tree import DecisionTreeEngine, DEFAULT_TARGET_CONFIDENCE_THRESHOLD
from src.pipeline.planner_models import DocumentPlan, IngestionConfig
from src.pipeline.artifact_exporter import (
    render_visual_overlays,
    export_interactive_html_viewer,
    export_pipeline_artifacts,
)


class PipelineExecutionResult(TypedDict, total=False):
    """Strongly-typed execution result container for pipeline extraction runs."""
    dom: Dict[str, Any]
    decision: Dict[str, Any]
    violations: List[Dict[str, Any]]
    dom_json_path: str
    violations_json_path: str
    plan_result_path: Optional[str]
    html_viewer_path: Optional[str]
    rendered_images: List[str]
    plan: Optional[Dict[str, Any]]


__all__ = [
    "IngestionConfig",
    "PipelineExecutionResult",
    "parse_document",
    "align_document_skew",
    "evaluate_quality_and_decision_tree",
    "render_visual_overlays",
    "export_interactive_html_viewer",
    "export_pipeline_artifacts",
    "run_pipeline",
]


def parse_document(
    pdf_path: str,
    language: Optional[str] = "en",
    preset: str = "docling_fast",
    ocr_engine: str = "auto",
    ocr_scale: Optional[float] = None,
    force_full_page_ocr: bool = False,
    do_table_structure: bool = True,
    config: Optional[IngestionConfig] = None,
) -> DocumentDOM:
    """Parses PDF document using the specified preset into DocumentDOM IR."""
    if config is not None:
        language = config.language
        preset = config.preset
        ocr_scale = config.ocr_scale if config.ocr_scale is not None else ocr_scale
        force_full_page_ocr = config.force_full_page_ocr
        do_table_structure = config.do_table_structure

    resolved_path = resolve_pdf_path(pdf_path)
    if not os.path.exists(resolved_path):
        raise FileNotFoundError(f"PDF document not found: '{pdf_path}'")

    if preset == "pypdfium_rapidocr":
        scale = ocr_scale if ocr_scale is not None else 2.0
        return PyPdfiumParser(language=language, scale=scale).parse(resolved_path)

    return DoclingParser(
        language=language,
        preset=preset,
        ocr_engine=ocr_engine,
        ocr_scale=ocr_scale,
        force_full_page_ocr=force_full_page_ocr,
        do_table_structure=do_table_structure,
    ).parse(resolved_path)


def align_document_skew(dom: DocumentDOM, pdf_path: str, align_skew: bool) -> DocumentDOM:
    """Auto-detects and applies local text line skew orientation angles per node."""
    if align_skew:
        return apply_text_skew_alignment(dom, pdf_path)
    return dom


def evaluate_quality_and_decision_tree(
    dom: DocumentDOM,
    target_threshold: float = DEFAULT_TARGET_CONFIDENCE_THRESHOLD,
    language: Optional[str] = "en",
    preset: str = "docling_fast",
    current_preset_score: float = 0.90,
    next_preset_score: float = 0.72,
    config: Optional[IngestionConfig] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Extracts quality violation records and evaluates confidence scores against target threshold."""
    if config is not None:
        target_threshold = config.target_threshold
        language = config.language
        preset = config.preset

    violations = detect_quality_violations(dom, language=language)
    engine = DecisionTreeEngine(
        target_threshold=target_threshold,
        current_preset_score=current_preset_score,
        next_preset_score=next_preset_score,
        language=language,
    )
    decision = engine.evaluate(dom)
    decision["chosen_preset"] = preset
    return decision, violations


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
) -> PipelineExecutionResult:
    """Executes end-to-end extraction pipeline with optional plan-driven execution and fallback orchestration."""
    plan_obj: Optional[DocumentPlan] = None
    if plan:
        if isinstance(plan, str):
            plan_obj = DocumentPlan.load(plan)
        elif isinstance(plan, dict):
            plan_obj = DocumentPlan.from_dict(plan)
        elif isinstance(plan, DocumentPlan):
            plan_obj = plan

    if not config:
        if plan_obj:
            config = plan_obj.to_ingestion_config(
                align_skew=align_skew,
                visualize=visualize,
                output_dir=output_dir,
            )
        else:
            config = IngestionConfig(
                target_threshold=target_threshold,
                language=language,
                preset=preset,
                align_skew=align_skew,
                visualize=visualize,
                output_dir=output_dir,
            )

    if not pdf_path and plan_obj and plan_obj.document_path:
        pdf_path = plan_obj.document_path

    if not pdf_path:
        raise ValueError("Input document path is required.")

    pdf_path = resolve_pdf_path(pdf_path)

    attempts: List[Dict[str, Any]] = []

    # Determine candidate scores and potential fallback candidate
    next_candidate = None
    part_of_plan = False
    if plan_obj and plan_obj.fallback_queue:
        first_fb = plan_obj.fallback_queue[0]
        next_candidate = first_fb.get("preset") if isinstance(first_fb, dict) else first_fb
        part_of_plan = True
    elif config.preset in ("docling_fast", "pypdfium_rapidocr"):
        next_candidate = "docling_deep"

    curr_score = plan_obj.scores.get(config.preset, 0.90) if plan_obj else 0.90
    next_score = plan_obj.scores.get(next_candidate, 0.72) if (plan_obj and next_candidate) else 0.72

    # Step 1: Initial Parse with Primary Preset
    dom, decision, violations = _execute_attempt(
        pdf_path, config, curr_score, next_score
    )
    attempts.append(_make_attempt_record(1, config.preset, decision, violations))

    if config.preset == "docling_deep":
        decision["chosen_preset"] = "docling_deep"
        decision["decision_tree"] = {
            "action": "ACCEPT_OUTPUT",
            "preset_executed": "docling_deep",
            "reason": "Executed using 'docling_deep' preset. All OCR diacritics restored."
        }
    elif not decision.get("is_accepted"):
        action = decision.get("decision_tree", {}).get("action")

        # Path B: Parameter Wiggling on current preset if delta is large
        if action == "PATH_B_WIGGLE_PARAMETERS":
            wiggled_scale = 3.5 if config.preset == "pypdfium_rapidocr" else 4.0
            wiggled_force_ocr = True
            wiggled_config = replace(
                config,
                ocr_scale=wiggled_scale,
                force_full_page_ocr=wiggled_force_ocr,
            )
            w_dom, w_decision, w_violations = _execute_attempt(
                pdf_path, wiggled_config, curr_score, next_score
            )
            attempts.append(_make_attempt_record(
                len(attempts) + 1, config.preset, w_decision, w_violations,
                action="PATH_B_WIGGLE_PARAMETERS",
                reason=f"Wiggled OCR parameters: ocr_scale={wiggled_scale}, force_full_page_ocr={wiggled_force_ocr}.",
                parameters={"ocr_scale": wiggled_scale, "force_full_page_ocr": wiggled_force_ocr}
            ))

            if w_decision.get("is_accepted"):
                dom, decision, violations = w_dom, w_decision, w_violations
                decision["decision_tree"] = {
                    "action": "ACCEPT_OUTPUT",
                    "preset_executed": config.preset,
                    "reason": f"Preset '{config.preset}' reached target threshold after parameter wiggling."
                }
            elif next_candidate:
                # Parameter wiggling exhausted, proceed to Path A (Preset Switch)
                plan_note = f"Executed fallback '{next_candidate}' after parameter wiggling."
                fallback_config = replace(config, preset=next_candidate)
                fb_dom, fb_decision, fb_violations = _execute_attempt(
                    pdf_path, fallback_config
                )
                fb_decision["decision_tree"] = {
                    "action": "PATH_A_SWITCH_PRESET",
                    "preset_executed": next_candidate,
                    "fallback_triggered": True,
                    "reason": plan_note,
                    "plan_status": "in_plan" if part_of_plan else "dynamic_fallback",
                    "detail": plan_note
                }
                attempts.append(_make_attempt_record(
                    len(attempts) + 1, next_candidate, fb_decision, fb_violations,
                    action=fb_decision.get("decision_tree", {}).get("action"),
                    reason=fb_decision.get("decision_tree", {}).get("reason"),
                    detail=plan_note
                ))
                dom, decision, violations = fb_dom, fb_decision, fb_violations
        elif next_candidate:
            # Path A: Switch to next candidate preset
            if part_of_plan:
                plan_note = f"Executed plan fallback '{next_candidate}'."
            else:
                plan_note = f"'{next_candidate}' wasn't part of the original plan, falling back to it."

            fallback_config = replace(config, preset=next_candidate)
            fb_dom, fb_decision, fb_violations = _execute_attempt(
                pdf_path, fallback_config
            )
            fb_decision["decision_tree"] = {
                "action": "PATH_A_SWITCH_PRESET",
                "preset_executed": next_candidate,
                "fallback_triggered": True,
                "reason": (
                    f"Initial preset '{config.preset}' fell below threshold "
                    f"({decision.get('overall_confidence')} < {config.target_threshold}). {plan_note}"
                ),
                "plan_status": "in_plan" if part_of_plan else "dynamic_fallback",
                "detail": plan_note
            }
            attempts.append(_make_attempt_record(
                len(attempts) + 1, next_candidate, fb_decision, fb_violations,
                action=fb_decision.get("decision_tree", {}).get("action"),
                reason=fb_decision.get("decision_tree", {}).get("reason"),
                detail=plan_note
            ))
            dom, decision, violations = fb_dom, fb_decision, fb_violations

    decision["attempts"] = attempts

    plan_dict = plan_obj.to_dict() if plan_obj else None
    rendered_images = render_visual_overlays(pdf_path, dom, violations, config.visualize, config.output_dir, decision=decision)
    dom_json_path, violations_json_path, plan_result_path = export_pipeline_artifacts(
        dom, decision, violations, config.language, config.output_dir, plan=plan_dict
    )
    html_viewer_path = export_interactive_html_viewer(pdf_path, dom, decision, violations, config.output_dir, plan=plan_dict)

    return {
        "dom": dom.to_dict(),
        "decision": decision,
        "violations": violations,
        "dom_json_path": dom_json_path,
        "violations_json_path": violations_json_path,
        "plan_result_path": plan_result_path,
        "html_viewer_path": html_viewer_path,
        "rendered_images": rendered_images,
        "plan": plan_dict
    }
