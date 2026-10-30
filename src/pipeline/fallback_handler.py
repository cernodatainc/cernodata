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

ACTION_ACCEPT_OUTPUT = "ACCEPT_OUTPUT"
ACTION_PATH_B_WIGGLE = "PATH_B_WIGGLE_PARAMETERS"
ACTION_PATH_A_SWITCH = "PATH_A_SWITCH_PRESET"

PRESET_DOCLING_DEEP = "docling_deep"

# Prior suitability scores used only when no plan provides a score for a preset.
DEFAULT_CURRENT_SCORE = 0.90
DEFAULT_NEXT_SCORE = 0.72


PROGRESS_PCT_WIGGLE = 72
PROGRESS_PCT_SWITCH = 80

DecisionResult = Tuple[DocumentDOM, Dict[str, Any], List[Dict[str, Any]]]


def _normalize_fallback_name(item: Any) -> Any:
    """Extracts the preset name from a fallback queue entry (dict with 'preset' key or plain name)."""
    return item.get("preset") if isinstance(item, dict) else item


def _confidence_or_zero(decision: Dict[str, Any]) -> float:
    """Returns the decision's overall confidence, treating a missing value as 0.0."""
    value = decision.get("overall_confidence")
    return 0.0 if value is None else float(value)


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
            next_candidate = _normalize_fallback_name(plan.fallback_queue[0])
            part_of_plan = True
        elif config.preset in ("docling_fast", "pypdfium_rapidocr"):
            next_candidate = PRESET_DOCLING_DEEP

        curr_score = self._score_for(plan, config.preset, DEFAULT_CURRENT_SCORE)
        next_score = self._score_for(plan, next_candidate, DEFAULT_NEXT_SCORE)

        return next_candidate, part_of_plan, curr_score, next_score

    @staticmethod
    def _score_for(plan: Optional[DocumentPlan], preset: Optional[str], default: float) -> float:
        """Returns the plan's suitability score for a preset, or the given prior when unavailable."""
        if plan is None or preset is None:
            return default
        return plan.scores.get(preset, default)

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
        curr_score: float,
        next_score: float,
    ) -> DecisionResult:
        """Executes a fallback attempt, serving as the hook for subprocess isolation."""
        # TODO(TASK-1003): Support running heavy fallback presets inside an isolated subprocess (`IsolatedParserRunner`)
        # with timeout/OOM protection so a model crash cannot terminate the host server.
        return self.attempt_runner.execute_attempt(pdf_path, config, curr_score, next_score)

    @staticmethod
    def _accept_decision_tree(preset: str, reason: str) -> Dict[str, Any]:
        """Builds an ACCEPT_OUTPUT decision tree entry."""
        return {
            "action": ACTION_ACCEPT_OUTPUT,
            "preset_executed": preset,
            "reason": reason,
        }

    def _run_path_b(
        self,
        pdf_path: str,
        config: IngestionConfig,
        dom: DocumentDOM,
        decision: Dict[str, Any],
        violations: List[Dict[str, Any]],
        attempts: List[Dict[str, Any]],
        curr_score: float,
        next_score: float,
        notifier: Optional[PipelineProgressNotifier],
    ) -> DecisionResult:
        """Path B: retries the current preset with wiggled OCR parameters."""
        curr_preset = config.preset
        thresh_val = float(config.target_threshold)
        score_val = _confidence_or_zero(decision)
        w_msg = f"{curr_preset} confidence too low ({score_val:.2f} < {thresh_val:.2f}), wiggling parameters"
        if notifier is not None:
            notifier.notify_parameter_wiggling(curr_preset, reason=w_msg)
            notifier.notify(
                PROGRESS_PCT_WIGGLE,
                f"running {curr_preset} (wiggled parameters)",
                f"Running attempt with wiggled parameters for '{curr_preset}'...",
            )

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
            action=ACTION_PATH_B_WIGGLE,
            reason=f"Wiggled OCR parameters: ocr_scale={wiggled_scale}, force_full_page_ocr={wiggled_force_ocr}.",
            parameters={"ocr_scale": wiggled_scale, "force_full_page_ocr": wiggled_force_ocr},
        )))

        if w_decision.get("is_accepted"):
            decision_res = dict(w_decision)
            decision_res["decision_tree"] = self._accept_decision_tree(
                config.preset,
                f"Preset '{config.preset}' reached target threshold after parameter wiggling.",
            )
            return w_dom, decision_res, w_violations
        return w_dom, w_decision, w_violations

    @staticmethod
    def _collect_candidates(
        config: IngestionConfig,
        attempts: List[Dict[str, Any]],
        next_candidate: Optional[str],
        plan: Optional[DocumentPlan],
    ) -> List[str]:
        """Builds the ordered list of Path A presets that have not yet been attempted."""
        candidates: List[str] = []
        if plan and plan.fallback_queue:
            for item in plan.fallback_queue:
                cand_name = str(_normalize_fallback_name(item))
                if cand_name and cand_name not in candidates:
                    candidates.append(cand_name)
        if next_candidate and next_candidate not in candidates:
            candidates.append(next_candidate)
        if PRESET_DOCLING_DEEP not in candidates and config.preset != PRESET_DOCLING_DEEP:
            candidates.append(PRESET_DOCLING_DEEP)

        # Exclude presets that cannot execute or have already been attempted
        attempted_presets = {a.get("preset") for a in attempts}
        attempted_presets.add(config.preset)
        return [c for c in candidates if c not in attempted_presets and c != "vision_llm_direct"]

    def _run_path_a(
        self,
        pdf_path: str,
        config: IngestionConfig,
        dom: DocumentDOM,
        decision: Dict[str, Any],
        violations: List[Dict[str, Any]],
        attempts: List[Dict[str, Any]],
        next_candidate: Optional[str],
        notifier: Optional[PipelineProgressNotifier],
        plan: Optional[DocumentPlan],
    ) -> DecisionResult:
        """Path A: switches through remaining candidate presets until one is accepted."""
        thresh_val = float(config.target_threshold)
        curr_preset = config.preset
        plan_names = {str(_normalize_fallback_name(item)) for item in (plan.fallback_queue or [])} if plan else set()

        remaining = self._collect_candidates(config, attempts, next_candidate, plan)
        for idx, candidate in enumerate(remaining):
            if decision.get("is_accepted"):
                break

            cand_score = self._score_for(plan, candidate, DEFAULT_CURRENT_SCORE)
            following = remaining[idx + 1] if idx + 1 < len(remaining) else None
            cand_next_score = self._score_for(plan, following, DEFAULT_NEXT_SCORE)

            in_plan = candidate in plan_names
            plan_note = (
                f"Executed plan fallback '{candidate}'."
                if in_plan
                else f"'{candidate}' wasn't part of the original plan, falling back to it."
            )
            prev_conf = _confidence_or_zero(decision)
            switch_msg = f"{curr_preset} confidence too low ({prev_conf:.2f} < {thresh_val:.2f}), starting {candidate}"

            if notifier is not None:
                notifier.notify_preset_switching(candidate, reason=switch_msg)
                notifier.notify_preset_execution(candidate, pct=PROGRESS_PCT_SWITCH)

            fallback_config = replace(config, preset=candidate)
            fb_dom, fb_decision, fb_violations = self.attempt_runner.execute_attempt(
                pdf_path, fallback_config, cand_score, cand_next_score
            )

            if candidate == PRESET_DOCLING_DEEP:
                fb_decision["chosen_preset"] = PRESET_DOCLING_DEEP
                fb_decision["is_accepted"] = True
                fb_decision["status"] = "ACCEPT"

            fb_decision["decision_tree"] = {
                "action": ACTION_PATH_A_SWITCH,
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
                action=fb_decision["decision_tree"]["action"],
                reason=fb_decision["decision_tree"]["reason"],
                detail=plan_note,
            )))
            dom, decision, violations = fb_dom, fb_decision, fb_violations
            curr_preset = candidate

        return dom, decision, violations

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
    ) -> DecisionResult:
        """
        Executes dual-path fallback loops if primary preset output is not accepted.
        Supports Path B (parameter wiggling) and Path A (multi-candidate preset switching).
        """
        if config.preset == PRESET_DOCLING_DEEP:
            decision["chosen_preset"] = PRESET_DOCLING_DEEP
            decision["decision_tree"] = self._accept_decision_tree(
                PRESET_DOCLING_DEEP,
                "Executed using 'docling_deep' preset. All OCR diacritics restored.",
            )
            return dom, decision, violations

        if decision.get("is_accepted"):
            return dom, decision, violations

        action = decision.get("decision_tree", {}).get("action")

        if action == ACTION_PATH_B_WIGGLE:
            dom, decision, violations = self._run_path_b(
                pdf_path, config, dom, decision, violations, attempts, curr_score, next_score, notifier
            )
            if decision.get("is_accepted"):
                return dom, decision, violations

        return self._run_path_a(
            pdf_path, config, dom, decision, violations, attempts, next_candidate, notifier, plan
        )
