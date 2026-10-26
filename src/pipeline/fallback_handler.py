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

    def _resolve_wiggle_parameters(self, config: IngestionConfig) -> Tuple[float, bool]:
        """Resolves OCR parameter wiggling bounds for Path B retries."""
        # TODO(TASK-206): Read custom parameter wiggling bounds (`ParameterWiggleSpec`) from `CustomPresetConfig`
        # instead of only wiggling `ocr_scale` and `force_full_page_ocr`.
        wiggled_scale = 3.5 if config.preset == "pypdfium_rapidocr" else 4.0
        return wiggled_scale, True

    def _slice_failing_pages_if_needed(
        self, pdf_path: str, dom: DocumentDOM, violations: List[Dict[str, Any]]
    ) -> str:
        """No-op hook returning full PDF path until targeted page slicing is wired into fallback retries."""
        # TODO(TASK-803): When only a subset of pages failed quality checks, slice just those pages via
        # `slice_pdf_pages` (TASK-801), run the fallback preset on the slice, and splice back via `merge_sliced_dom` (TASK-802).
        _ = (dom, violations)
        return pdf_path

    def _execute_isolated_attempt(
        self,
        pdf_path: str,
        config: IngestionConfig,
        curr_score: float = 0.90,
        next_score: float = 0.72,
    ) -> Tuple[DocumentDOM, Dict[str, Any], List[Dict[str, Any]]]:
        """Executes a fallback attempt, serving as the hook for subprocess isolation."""
        # TODO(TASK-1003): Support running heavy fallback presets inside an isolated subprocess (`IsolatedParserRunner`)
        # with timeout/OOM protection so a model crash cannot terminate the host server.
        return self.attempt_runner.execute_attempt(pdf_path, config, curr_score, next_score)

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
        plan: Optional[DocumentPlan] = None,
    ) -> Tuple[DocumentDOM, Dict[str, Any], List[Dict[str, Any]]]:
        """
        Executes dual-path fallback loops if primary preset output is not accepted.
        Supports Path B (parameter wiggling) and Path A (multi-candidate preset switching).
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
        thresh_val = float(config.target_threshold)
        curr_preset = config.preset

        # Path B: Parameter Wiggling on current preset if delta is large
        if action == "PATH_B_WIGGLE_PARAMETERS":
            score_val = float(decision.get("overall_confidence", 0.0) or 0.0)
            w_msg = f"{curr_preset} confidence too low ({score_val:.2f} < {thresh_val:.2f}), wiggling parameters"
            if notifier is not None:
                notifier.notify_parameter_wiggling(curr_preset, reason=w_msg)
                notifier.notify(72, f"running {curr_preset} (wiggled parameters)", f"Running attempt with wiggled parameters for '{curr_preset}'...")

            wiggled_scale, wiggled_force_ocr = self._resolve_wiggle_parameters(config)
            target_pdf = self._slice_failing_pages_if_needed(pdf_path, dom, violations)
            wiggled_config = replace(
                config,
                ocr_scale=wiggled_scale,
                force_full_page_ocr=wiggled_force_ocr,
            )
            w_dom, w_decision, w_violations = self._execute_isolated_attempt(
                target_pdf, wiggled_config, curr_score, next_score
            )
            attempts.append(dict(self.attempt_runner.make_attempt_record(
                len(attempts) + 1, config.preset, w_decision, w_violations,
                action="PATH_B_WIGGLE_PARAMETERS",
                reason=f"Wiggled OCR parameters: ocr_scale={wiggled_scale}, force_full_page_ocr={wiggled_force_ocr}.",
                parameters={"ocr_scale": wiggled_scale, "force_full_page_ocr": wiggled_force_ocr},
            )))

            if w_decision.get("is_accepted"):
                decision_res = dict(w_decision)
                decision_res["decision_tree"] = {
                    "action": "ACCEPT_OUTPUT",
                    "preset_executed": config.preset,
                    "reason": f"Preset '{config.preset}' reached target threshold after parameter wiggling.",
                }
                return w_dom, decision_res, w_violations
            dom, decision, violations = w_dom, w_decision, w_violations

        # Path A: Multi-candidate preset switching loop
        candidates: List[str] = []
        if plan and plan.fallback_queue:
            for item in plan.fallback_queue:
                cand_name = str(item.get("preset") if isinstance(item, dict) else item)
                if cand_name and cand_name not in candidates:
                    candidates.append(cand_name)
        if next_candidate and next_candidate not in candidates:
            candidates.append(next_candidate)
        if "docling_deep" not in candidates and config.preset != "docling_deep":
            candidates.append("docling_deep")

        # Exclude presets that cannot execute or have already been attempted
        attempted_presets = {a.get("preset") for a in attempts}
        attempted_presets.add(config.preset)
        remaining_candidates = [c for c in candidates if c not in attempted_presets and c != "vision_llm_direct"]

        for candidate in remaining_candidates:
            if decision.get("is_accepted"):
                break

            in_plan = bool(plan and any(
                str(item.get("preset") if isinstance(item, dict) else item) == candidate
                for item in (plan.fallback_queue or [])
            ))
            plan_note = f"Executed plan fallback '{candidate}'." if in_plan else f"'{candidate}' wasn't part of the original plan, falling back to it."
            prev_conf = float(decision.get("overall_confidence", 0.0) or 0.0)
            switch_msg = f"{curr_preset} confidence too low ({prev_conf:.2f} < {thresh_val:.2f}), starting {candidate}"

            if notifier is not None:
                notifier.notify_preset_switching(candidate, reason=switch_msg)
                notifier.notify_preset_execution(candidate, pct=80)

            fallback_config = replace(config, preset=candidate)
            fb_dom, fb_decision, fb_violations = self.attempt_runner.execute_attempt(
                pdf_path, fallback_config
            )

            if candidate == "docling_deep":
                fb_decision["chosen_preset"] = "docling_deep"
                fb_decision["is_accepted"] = True
                fb_decision["status"] = "ACCEPT"

            fb_decision["decision_tree"] = {
                "action": "PATH_A_SWITCH_PRESET",
                "preset_executed": candidate,
                "fallback_triggered": True,
                "reason": (
                    f"Previous preset fell below threshold "
                    f"({prev_conf:.4f} < {config.target_threshold}). {plan_note}"
                ),
                "plan_status": "in_plan" if in_plan else "dynamic_fallback",
                "detail": plan_note,
            }
            attempts.append(dict(self.attempt_runner.make_attempt_record(
                len(attempts) + 1, candidate, fb_decision, fb_violations,
                action=fb_decision.get("decision_tree", {}).get("action"),
                reason=fb_decision.get("decision_tree", {}).get("reason"),
                detail=plan_note,
            )))
            dom, decision, violations = fb_dom, fb_decision, fb_violations
            curr_preset = candidate

        return dom, decision, violations
