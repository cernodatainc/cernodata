"""
src/pipeline/orchestrator.py

End-to-end pipeline runner orchestrating parsing, text skew alignment, quality evaluation, exports, and rendering.
Supports executing custom and planner-generated execution plans.
"""

from typing import Dict, Any, List, Tuple, Optional, Union

from src.dom import DocumentDOM
from src.parsers import DoclingParser, PyPdfiumParser
from src.quality import detect_quality_violations, apply_text_skew_alignment
from src.pipeline.decision_tree import DecisionTreeEngine, DEFAULT_TARGET_CONFIDENCE_THRESHOLD
from src.pipeline.planner import DocumentPlan
from src.pipeline.artifact_exporter import (
    render_visual_overlays,
    export_interactive_html_viewer,
    export_pipeline_artifacts,
)

__all__ = [
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
    language: str,
    preset: str = "docling_fast",
    ocr_engine: str = "auto",
    ocr_scale: Optional[float] = None,
    force_full_page_ocr: bool = False,
    do_table_structure: bool = True,
) -> DocumentDOM:
    """Parses PDF document using the specified preset into DocumentDOM IR."""
    if preset == "pypdfium_rapidocr":
        scale = ocr_scale if ocr_scale is not None else 2.0
        parser = PyPdfiumParser(language=language, scale=scale)
        return parser.parse(pdf_path)

    parser = DoclingParser(
        language=language,
        preset=preset,
        ocr_engine=ocr_engine,
        ocr_scale=ocr_scale,
        force_full_page_ocr=force_full_page_ocr,
        do_table_structure=do_table_structure,
    )
    return parser.parse(pdf_path)


def align_document_skew(dom: DocumentDOM, pdf_path: str, align_skew: bool) -> DocumentDOM:
    """Auto-detects and applies local text line skew orientation angles per node."""
    if align_skew:
        return apply_text_skew_alignment(dom, pdf_path)
    return dom


def evaluate_quality_and_decision_tree(
    dom: DocumentDOM,
    target_threshold: float,
    language: str,
    preset: str = "docling_fast",
    current_preset_score: float = 0.90,
    next_preset_score: float = 0.72,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Extracts quality violation records and evaluates confidence scores against target threshold."""
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


def run_pipeline(
    pdf_path: Optional[str] = None,
    target_threshold: float = DEFAULT_TARGET_CONFIDENCE_THRESHOLD,
    language: str = "en",
    preset: str = "docling_fast",
    align_skew: bool = True,
    visualize: bool = True,
    output_dir: str = "output",
    plan: Optional[Union[str, Dict[str, Any], DocumentPlan]] = None
) -> Dict[str, Any]:
    """Executes end-to-end extraction pipeline with optional plan-driven execution and fallback orchestration."""
    plan_obj: Optional[DocumentPlan] = None
    if plan:
        if isinstance(plan, str):
            plan_obj = DocumentPlan.load(plan)
        elif isinstance(plan, dict):
            plan_obj = DocumentPlan.from_dict(plan)
        elif isinstance(plan, DocumentPlan):
            plan_obj = plan

    if plan_obj:
        if not pdf_path and plan_obj.document_path:
            pdf_path = plan_obj.document_path
        language = plan_obj.language
        target_threshold = plan_obj.target_threshold
        preset = plan_obj.primary_preset

    if not pdf_path:
        raise ValueError("Input document path is required.")

    attempts: List[Dict[str, Any]] = []

    # Determine candidate scores and potential fallback candidate
    next_candidate = None
    part_of_plan = False
    if plan_obj and plan_obj.fallback_queue:
        first_fb = plan_obj.fallback_queue[0]
        next_candidate = first_fb.get("preset") if isinstance(first_fb, dict) else first_fb
        part_of_plan = True
    elif preset in ("docling_fast", "pypdfium_rapidocr"):
        next_candidate = "docling_deep"

    curr_score = plan_obj.scores.get(preset, 0.90) if plan_obj else 0.90
    next_score = plan_obj.scores.get(next_candidate, 0.72) if (plan_obj and next_candidate) else 0.72

    # Step 1: Initial Parse with Primary Preset
    dom = parse_document(pdf_path, language, preset=preset)
    dom = align_document_skew(dom, pdf_path, align_skew)
    decision, violations = evaluate_quality_and_decision_tree(
        dom,
        target_threshold,
        language,
        preset=preset,
        current_preset_score=curr_score,
        next_preset_score=next_score,
    )

    initial_attempt = {
        "step": 1,
        "preset": preset,
        "overall_confidence": decision.get("overall_confidence"),
        "per_page_confidence": decision.get("per_page_confidence"),
        "status": decision.get("status"),
        "is_accepted": decision.get("is_accepted", False),
        "violations_count": len(violations),
        "action": decision.get("decision_tree", {}).get("action"),
        "reason": decision.get("decision_tree", {}).get("reason")
    }
    attempts.append(initial_attempt)

    if preset == "docling_deep":
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
            wiggled_scale = 3.5 if preset == "pypdfium_rapidocr" else 4.0
            wiggled_force_ocr = True
            w_dom = parse_document(
                pdf_path,
                language,
                preset=preset,
                ocr_scale=wiggled_scale,
                force_full_page_ocr=wiggled_force_ocr,
            )
            w_dom = align_document_skew(w_dom, pdf_path, align_skew)
            w_decision, w_violations = evaluate_quality_and_decision_tree(
                w_dom,
                target_threshold,
                language,
                preset=preset,
                current_preset_score=curr_score,
                next_preset_score=next_score,
            )
            w_decision["chosen_preset"] = preset

            w_attempt = {
                "step": len(attempts) + 1,
                "preset": preset,
                "overall_confidence": w_decision.get("overall_confidence"),
                "per_page_confidence": w_decision.get("per_page_confidence"),
                "status": w_decision.get("status"),
                "is_accepted": w_decision.get("is_accepted", False),
                "violations_count": len(w_violations),
                "action": "PATH_B_WIGGLE_PARAMETERS",
                "reason": f"Wiggled OCR parameters: ocr_scale={wiggled_scale}, force_full_page_ocr={wiggled_force_ocr}.",
                "parameters": {"ocr_scale": wiggled_scale, "force_full_page_ocr": wiggled_force_ocr}
            }
            attempts.append(w_attempt)

            if w_decision.get("is_accepted"):
                dom = w_dom
                decision = w_decision
                violations = w_violations
                decision["decision_tree"] = {
                    "action": "ACCEPT_OUTPUT",
                    "preset_executed": preset,
                    "reason": f"Preset '{preset}' reached target threshold after parameter wiggling."
                }
            elif next_candidate:
                # Parameter wiggling exhausted, proceed to Path A (Preset Switch)
                fallback_dom = parse_document(pdf_path, language, preset=next_candidate)
                fallback_dom = align_document_skew(fallback_dom, pdf_path, align_skew)
                fb_decision, fb_violations = evaluate_quality_and_decision_tree(
                    fallback_dom, target_threshold, language, preset=next_candidate
                )
                fb_decision["chosen_preset"] = next_candidate
                plan_note = f"Executed fallback '{next_candidate}' after parameter wiggling."
                fb_decision["decision_tree"] = {
                    "action": "PATH_A_SWITCH_PRESET",
                    "preset_executed": next_candidate,
                    "fallback_triggered": True,
                    "reason": plan_note,
                    "plan_status": "in_plan" if part_of_plan else "dynamic_fallback",
                    "detail": plan_note
                }
                fb_attempt = {
                    "step": len(attempts) + 1,
                    "preset": next_candidate,
                    "overall_confidence": fb_decision.get("overall_confidence"),
                    "per_page_confidence": fb_decision.get("per_page_confidence"),
                    "status": fb_decision.get("status"),
                    "is_accepted": fb_decision.get("is_accepted", False),
                    "violations_count": len(fb_violations),
                    "action": fb_decision.get("decision_tree", {}).get("action"),
                    "reason": fb_decision.get("decision_tree", {}).get("reason"),
                    "detail": plan_note
                }
                attempts.append(fb_attempt)
                dom = fallback_dom
                decision = fb_decision
                violations = fb_violations
        elif next_candidate:
            # Path A: Switch to next candidate preset
            fallback_dom = parse_document(pdf_path, language, preset=next_candidate)
            fallback_dom = align_document_skew(fallback_dom, pdf_path, align_skew)
            fb_decision, fb_violations = evaluate_quality_and_decision_tree(
                fallback_dom, target_threshold, language, preset=next_candidate
            )
            fb_decision["chosen_preset"] = next_candidate

            if part_of_plan:
                plan_note = f"Executed plan fallback '{next_candidate}'."
            else:
                plan_note = f"'{next_candidate}' wasn't part of the original plan, falling back to it."

            fb_decision["decision_tree"] = {
                "action": "PATH_A_SWITCH_PRESET",
                "preset_executed": next_candidate,
                "fallback_triggered": True,
                "reason": (
                    f"Initial preset '{preset}' fell below threshold "
                    f"({decision.get('overall_confidence')} < {target_threshold}). {plan_note}"
                ),
                "plan_status": "in_plan" if part_of_plan else "dynamic_fallback",
                "detail": plan_note
            }

            second_attempt = {
                "step": len(attempts) + 1,
                "preset": next_candidate,
                "overall_confidence": fb_decision.get("overall_confidence"),
                "per_page_confidence": fb_decision.get("per_page_confidence"),
                "status": fb_decision.get("status"),
                "is_accepted": fb_decision.get("is_accepted", False),
                "violations_count": len(fb_violations),
                "action": fb_decision.get("decision_tree", {}).get("action"),
                "reason": fb_decision.get("decision_tree", {}).get("reason"),
                "detail": plan_note
            }
            attempts.append(second_attempt)

            dom = fallback_dom
            decision = fb_decision
            violations = fb_violations

    decision["attempts"] = attempts

    plan_dict = plan_obj.to_dict() if plan_obj else None
    rendered_images = render_visual_overlays(pdf_path, dom, violations, visualize, output_dir, decision=decision)
    dom_json_path, violations_json_path, plan_result_path = export_pipeline_artifacts(
        dom, decision, violations, language, output_dir, plan=plan_dict
    )
    html_viewer_path = export_interactive_html_viewer(pdf_path, dom, decision, violations, output_dir, plan=plan_dict)

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
