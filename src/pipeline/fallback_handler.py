"""
src/pipeline/fallback_handler.py

Confidence-guided fallback orchestration, parameter wiggling, and preset switching loops.
"""

from dataclasses import replace
from typing import Any, Dict, List, Optional, Tuple

from src.dom import DocumentDOM
from src.pipeline.attempt_runner import AttemptRunner
from src.pipeline.planner.models import DocumentPlan, IngestionConfig
from src.pipeline.progress_notifier import PipelineProgressNotifier


class FallbackLoopHandler:
    """Manages confidence-guided fallback iteration loops (Path A and Path B)."""

    def __init__(self, attempt_runner: Optional[AttemptRunner] = None) -> None:
        self.attempt_runner = attempt_runner or AttemptRunner()

    def resolve_candidate_scores(
        self,
        config: IngestionConfig,
        plan: Optional[DocumentPlan] = None,
    ) -> Tuple[Optional[str], bool, float, float]:
        """Resolves next fallback candidate, whether it's part of plan, and suitability scores."""
        next_candidate: Optional[str] = None
        part_of_plan = False

        if plan and plan.fallback_queue:
            first_fb = plan.fallback_queue[0]
            next_candidate = first_fb.get("preset") if isinstance(first_fb, dict) else first_fb
            part_of_plan = True
        elif config.preset in ("docling_fast", "pypdfium_rapidocr"):
            next_candidate = "docling_deep"

        curr_score = plan.scores.get(config.preset, 0.90) if plan else 0.90
        next_score = plan.scores.get(next_candidate, 0.72) if (plan and next_candidate) else 0.72

        return next_candidate, part_of_plan, curr_score, next_score

    def handle_fallback(
        self,
        pdf_path: str,
        config: IngestionConfig,
        dom: DocumentDOM,
        decision: Dict[str, Any],
        violations: List[Dict[str, Any]],
        attempts: List[Dict[str, Any]],
        next_candidate: Optional[str],
        part_of_plan: bool,
        curr_score: float,
        next_score: float,
        notifier: Optional[PipelineProgressNotifier] = None,
    ) -> Tuple[DocumentDOM, Dict[str, Any], List[Dict[str, Any]]]:
        """
        Executes dual-path fallback loops if primary preset output is not accepted.
        Supports Path B (parameter wiggling) and Path A (preset switching).
        """
        if config.preset == "docling_deep":
            decision["chosen_preset"] = "docling_deep"
            decision["decision_tree"] = {
                "action": "ACCEPT_OUTPUT",
                "preset_executed": "docling_deep",
                "reason": "Executed using 'docling_deep' preset. All OCR diacritics restored.",
            }
            return dom, decision, violations

        if decision.get("is_accepted"):
            return dom, decision, violations

        action = decision.get("decision_tree", {}).get("action")

        # Path B: Parameter Wiggling on current preset if delta is large
        if action == "PATH_B_WIGGLE_PARAMETERS":
            if notifier is not None:
                notifier.notify_parameter_wiggling(config.preset)

            wiggled_scale = 3.5 if config.preset == "pypdfium_rapidocr" else 4.0
            wiggled_force_ocr = True
            wiggled_config = replace(
                config,
                ocr_scale=wiggled_scale,
                force_full_page_ocr=wiggled_force_ocr,
            )
            w_dom, w_decision, w_violations = self.attempt_runner.execute_attempt(
                pdf_path, wiggled_config, curr_score, next_score
            )
            attempts.append(dict(self.attempt_runner.make_attempt_record(
                len(attempts) + 1, config.preset, w_decision, w_violations,
                action="PATH_B_WIGGLE_PARAMETERS",
                reason=f"Wiggled OCR parameters: ocr_scale={wiggled_scale}, force_full_page_ocr={wiggled_force_ocr}.",
                parameters={"ocr_scale": wiggled_scale, "force_full_page_ocr": wiggled_force_ocr},
            )))

            if w_decision.get("is_accepted"):
                dom, decision, violations = w_dom, w_decision, w_violations
                decision["decision_tree"] = {
                    "action": "ACCEPT_OUTPUT",
                    "preset_executed": config.preset,
                    "reason": f"Preset '{config.preset}' reached target threshold after parameter wiggling.",
                }
            elif next_candidate:
                # Parameter wiggling exhausted, proceed to Path A (Preset Switch)
                plan_note = f"Executed fallback '{next_candidate}' after parameter wiggling."
                if notifier is not None:
                    notifier.notify_preset_switching(next_candidate, reason="Wiggling exhausted.")

                fallback_config = replace(config, preset=next_candidate)
                fb_dom, fb_decision, fb_violations = self.attempt_runner.execute_attempt(
                    pdf_path, fallback_config
                )
                fb_decision["decision_tree"] = {
                    "action": "PATH_A_SWITCH_PRESET",
                    "preset_executed": next_candidate,
                    "fallback_triggered": True,
                    "reason": plan_note,
                    "plan_status": "in_plan" if part_of_plan else "dynamic_fallback",
                    "detail": plan_note,
                }
                attempts.append(dict(self.attempt_runner.make_attempt_record(
                    len(attempts) + 1, next_candidate, fb_decision, fb_violations,
                    action=fb_decision.get("decision_tree", {}).get("action"),
                    reason=fb_decision.get("decision_tree", {}).get("reason"),
                    detail=plan_note,
                )))
                dom, decision, violations = fb_dom, fb_decision, fb_violations
        elif next_candidate:
            # Path A: Switch to next candidate preset
            if part_of_plan:
                plan_note = f"Executed plan fallback '{next_candidate}'."
            else:
                plan_note = f"'{next_candidate}' wasn't part of the original plan, falling back to it."

            if notifier is not None:
                notifier.notify_preset_switching(
                    next_candidate,
                    reason=f"Target threshold not met ({decision.get('overall_confidence')} < {config.target_threshold})."
                )

            fallback_config = replace(config, preset=next_candidate)
            fb_dom, fb_decision, fb_violations = self.attempt_runner.execute_attempt(
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
                "detail": plan_note,
            }
            attempts.append(dict(self.attempt_runner.make_attempt_record(
                len(attempts) + 1, next_candidate, fb_decision, fb_violations,
                action=fb_decision.get("decision_tree", {}).get("action"),
                reason=fb_decision.get("decision_tree", {}).get("reason"),
                detail=plan_note,
            )))
            dom, decision, violations = fb_dom, fb_decision, fb_violations

        return dom, decision, violations
