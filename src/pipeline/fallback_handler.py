"""
src/pipeline/fallback_handler.py

Confidence-guided fallback orchestration, parameter wiggling, and preset switching loops.
"""

import logging
from dataclasses import replace
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

logger = logging.getLogger("cernodata.pipeline.fallback_handler")

from src.dom import DocumentDOM
from src.pipeline.attempt_runner import AttemptRunner
from src.pipeline.parsers.registry import get_default_parser_registry
from src.pipeline.planner.models import DocumentPlan, IngestionConfig
from src.pipeline.progress_notifier import PipelineProgressNotifier
from src.schemas.custom_preset import (
    CustomPresetConfig,
    ParameterWiggleSpec,
    load_custom_presets_file,
)

ACTION_ACCEPT_OUTPUT = "ACCEPT_OUTPUT"
ACTION_PATH_B_WIGGLE = "PATH_B_WIGGLE_PARAMETERS"
ACTION_PATH_A_SWITCH = "PATH_A_SWITCH_PRESET"

PROGRESS_PCT_WIGGLE = 72
PROGRESS_PCT_SWITCH = 80

DEFAULT_WIGGLE_SCALE_RAPIDOCR = 3.5
DEFAULT_WIGGLE_SCALE_DEFAULT = 4.0
NON_FALLBACK_PRESETS: frozenset[str] = frozenset({"vision_llm_direct"})

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
        effective_plan = plan
        part_of_plan = False
        if effective_plan and effective_plan.fallback_queue:
            part_of_plan = True
        else:
            from src.pipeline.planner import PresetPlanner
            effective_plan = PresetPlanner().create_plan(
                target_threshold=config.target_threshold,
                language=config.language,
                override_primary=config.preset,
            )

        next_candidate: Optional[str] = None
        if effective_plan and effective_plan.fallback_queue:
            next_candidate = str(_normalize_fallback_name(effective_plan.fallback_queue[0]))

        curr_score = self._score_for(effective_plan, config.preset)
        next_score = self._score_for(effective_plan, next_candidate)

        return next_candidate, part_of_plan, curr_score, next_score

    @classmethod
    def _score_for(
        cls,
        plan: Optional[DocumentPlan],
        preset: Optional[str],
    ) -> float:
        """Returns the plan's suitability score for a preset, or calculates it via PresetPlanner."""
        if preset is None:
            return 0.0
        if plan is not None and preset in plan.scores:
            return float(plan.scores[preset])
        from src.pipeline.planner import PresetPlanner
        scores = PresetPlanner().calculate_scores()
        return float(scores.get(preset, 0.50))

    def _get_custom_preset_config(self, config: IngestionConfig) -> Optional[CustomPresetConfig]:
        """Resolves CustomPresetConfig from config options, registries, or manifest path."""
        inline_cfg = config.options.get("custom_preset_config") or config.options.get("custom_preset")
        if isinstance(inline_cfg, CustomPresetConfig):
            return inline_cfg
        if isinstance(inline_cfg, Mapping):
            return CustomPresetConfig.from_dict(inline_cfg)

        parse_self = getattr(getattr(self.attempt_runner, "_parse_fn", None), "__self__", None)
        bound_registry = getattr(parse_self, "_registry", None)
        if bound_registry is not None and hasattr(bound_registry, "get_custom_preset"):
            found = bound_registry.get_custom_preset(config.preset)
            if isinstance(found, CustomPresetConfig):
                return found

        default_found = get_default_parser_registry().get_custom_preset(config.preset)
        if default_found is not None:
            return default_found

        if config.custom_presets_path:
            for item in load_custom_presets_file(config.custom_presets_path):
                if item.preset_id == config.preset:
                    return item
        return None

    def _get_wiggle_specs(self, config: IngestionConfig) -> List[ParameterWiggleSpec]:
        """Collects ParameterWiggleSpec entries from custom preset config or options."""
        custom_cfg = self._get_custom_preset_config(config)
        if custom_cfg is not None and custom_cfg.wiggle_parameters:
            return list(custom_cfg.wiggle_parameters)

        raw_specs = config.options.get("wiggle_specs")
        if raw_specs is None and isinstance(config.options.get("wiggle_parameters"), Sequence):
            if not isinstance(config.options.get("wiggle_parameters"), (str, bytes)):
                raw_specs = config.options.get("wiggle_parameters")
        if not isinstance(raw_specs, Sequence) or isinstance(raw_specs, (str, bytes)):
            return []

        specs: List[ParameterWiggleSpec] = []
        for entry in raw_specs:
            if isinstance(entry, ParameterWiggleSpec):
                specs.append(entry)
            elif isinstance(entry, Mapping):
                specs.append(ParameterWiggleSpec.from_dict(entry))
        return specs

    def _resolve_custom_wiggle_sets(self, config: IngestionConfig) -> List[Dict[str, Any]]:
        """Builds ordered parameter dictionaries for custom ParameterWiggleSpec fallback attempts."""
        specs = self._get_wiggle_specs(config)
        if not specs:
            return []

        base_defaults: Dict[str, Any] = {
            spec.name: spec.default_value
            for spec in specs
            if spec.default_value is not None
        }
        raw_extra = config.options.get("extra_parameters")
        if isinstance(raw_extra, Mapping):
            base_defaults.update({str(k): v for k, v in raw_extra.items()})

        candidates: List[Dict[str, Any]] = []
        seen_keys: set[str] = set()
        for spec in specs:
            current_val = base_defaults.get(spec.name, spec.default_value)
            for fallback_val in spec.fallback_values:
                if fallback_val == current_val:
                    continue
                candidate = dict(base_defaults)
                candidate[spec.name] = fallback_val
                sig = repr(sorted((str(k), repr(v)) for k, v in candidate.items()))
                if sig not in seen_keys:
                    seen_keys.add(sig)
                    candidates.append(candidate)
        return candidates

    def _resolve_wiggle_parameters(self, config: IngestionConfig) -> Tuple[float, bool]:
        """Resolves OCR parameter wiggling bounds for Path B retries."""
        for spec in self._get_wiggle_specs(config):
            if spec.name.lower() in ("ocr_scale", "scale") and spec.fallback_values:
                return float(spec.fallback_values[0]), True

        custom_scale = config.get_option("wiggle_scale") if hasattr(config, "get_option") else None
        if custom_scale is not None:
            wiggled_scale = float(custom_scale)
        elif config.preset == "pypdfium_rapidocr":
            wiggled_scale = DEFAULT_WIGGLE_SCALE_RAPIDOCR
        else:
            wiggled_scale = DEFAULT_WIGGLE_SCALE_DEFAULT
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
        next_preset_id: Optional[str] = None,
    ) -> DecisionResult:
        """Executes a fallback attempt, serving as the hook for subprocess isolation."""
        # TODO(TASK-1003): Support running heavy fallback presets inside an isolated subprocess (`IsolatedParserRunner`)
        # with timeout/OOM protection so a model crash cannot terminate the host server.
        return self.attempt_runner.execute_attempt(
            pdf_path,
            config,
            curr_score,
            next_score,
            next_preset_id=next_preset_id,
        )

    @staticmethod
    def _accept_decision_tree(preset: str, reason: str) -> Dict[str, Any]:
        """Builds an ACCEPT_OUTPUT decision tree entry."""
        return {
            "action": ACTION_ACCEPT_OUTPUT,
            "preset_executed": preset,
            "reason": reason,
        }

    def _build_wiggled_config(
        self,
        config: IngestionConfig,
        param_set: Dict[str, Any],
    ) -> IngestionConfig:
        """Creates an IngestionConfig copy carrying a single custom wiggle parameter set."""
        next_options = dict(config.options)
        raw_extra = config.options.get("extra_parameters")
        merged_extra = dict(raw_extra) if isinstance(raw_extra, Mapping) else {}
        merged_extra.update(param_set)
        next_options["extra_parameters"] = merged_extra
        next_options["wiggle_parameters"] = dict(merged_extra)

        raw_scale = merged_extra.get("ocr_scale", merged_extra.get("scale"))
        raw_force = merged_extra.get("force_full_page_ocr")
        return replace(
            config,
            ocr_scale=float(raw_scale) if raw_scale is not None else config.ocr_scale,
            force_full_page_ocr=(
                bool(raw_force) if raw_force is not None else config.force_full_page_ocr
            ),
            options=next_options,
        )

    def _run_custom_wiggle_attempts(
        self,
        target_pdf: str,
        config: IngestionConfig,
        wiggle_sets: List[Dict[str, Any]],
        attempts: List[Dict[str, Any]],
        curr_score: float,
        next_score: float,
    ) -> DecisionResult:
        """Iterates through CustomPresetConfig wiggle parameter sets for Path B retries."""
        best_result: Optional[DecisionResult] = None
        best_score = -1.0

        for param_set in wiggle_sets:
            wiggled_config = self._build_wiggled_config(config, param_set)
            w_dom, w_decision, w_violations = self._execute_isolated_attempt(
                target_pdf,
                wiggled_config,
                curr_score,
                next_score,
                next_preset_id=config.preset,
            )
            summary = ", ".join(f"{k}={v}" for k, v in param_set.items())
            attempts.append(dict(self.attempt_runner.make_attempt_record(
                len(attempts) + 1,
                config.preset,
                w_decision,
                w_violations,
                action=ACTION_PATH_B_WIGGLE,
                reason=f"Wiggled custom parameters: {summary}.",
                parameters=dict(param_set),
            )))
            if w_decision.get("is_accepted"):
                decision_res = dict(w_decision)
                decision_res["decision_tree"] = self._accept_decision_tree(
                    config.preset,
                    f"Preset '{config.preset}' reached target threshold after parameter wiggling ({summary}).",
                )
                return w_dom, decision_res, w_violations

            candidate_score = _confidence_or_zero(w_decision)
            if best_result is None or candidate_score >= best_score:
                best_score = candidate_score
                best_result = (w_dom, w_decision, w_violations)

        if best_result is None:
            raise ValueError("wiggle_sets must not be empty.")
        return best_result

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

        target_pdf = self._slice_failing_pages_if_needed(pdf_path, dom, violations)
        custom_wiggle_sets = self._resolve_custom_wiggle_sets(config)
        if custom_wiggle_sets:
            return self._run_custom_wiggle_attempts(
                target_pdf, config, custom_wiggle_sets, attempts, curr_score, next_score,
            )

        wiggled_scale, wiggled_force_ocr = self._resolve_wiggle_parameters(config)
        wiggled_config = replace(config, ocr_scale=wiggled_scale, force_full_page_ocr=wiggled_force_ocr)
        w_dom, w_decision, w_violations = self._execute_isolated_attempt(
            target_pdf, wiggled_config, curr_score, next_score, next_preset_id=config.preset,
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

    @classmethod
    def _collect_candidates(
        cls,
        config: IngestionConfig,
        attempts: List[Dict[str, Any]],
        next_candidate: Optional[str],
        plan: Optional[DocumentPlan],
    ) -> List[str]:
        """Builds the ordered list of Path A presets that have not yet been attempted."""
        candidates: List[str] = []
        effective_plan = plan
        if effective_plan is None or not effective_plan.fallback_queue:
            from src.pipeline.planner import PresetPlanner
            effective_plan = PresetPlanner().create_plan(
                target_threshold=config.target_threshold,
                language=config.language,
                override_primary=config.preset,
            )
        if effective_plan and effective_plan.fallback_queue:
            for item in effective_plan.fallback_queue:
                cand_name = str(_normalize_fallback_name(item))
                if cand_name and cand_name not in candidates:
                    candidates.append(cand_name)
        if next_candidate and next_candidate not in candidates:
            candidates.append(next_candidate)

        # Exclude presets that cannot execute or have already been attempted
        attempted_presets = {a.get("preset") for a in attempts}
        attempted_presets.add(config.preset)
        return [c for c in candidates if c not in attempted_presets and c not in NON_FALLBACK_PRESETS]

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
        plan_names = {str(_normalize_fallback_name(item)) for item in plan.fallback_queue} if plan else set()

        best_dom, best_decision, best_violations = dom, decision, violations
        best_conf = _confidence_or_zero(decision)
        prev_conf = best_conf

        remaining = self._collect_candidates(config, attempts, next_candidate, plan)
        for idx, candidate in enumerate(remaining):
            if best_decision.get("is_accepted"):
                break

            cand_score = self._score_for(plan, candidate)
            following = remaining[idx + 1] if idx + 1 < len(remaining) else None
            cand_next_score = self._score_for(plan, following)

            in_plan = candidate in plan_names
            plan_note = (
                f"Executed plan fallback '{candidate}'."
                if in_plan
                else f"'{candidate}' wasn't part of the original plan, falling back to it."
            )
            switch_msg = f"{curr_preset} confidence too low ({prev_conf:.2f} < {thresh_val:.2f}), starting {candidate}"

            if notifier is not None:
                notifier.notify_preset_switching(candidate, reason=switch_msg)
                notifier.notify_preset_execution(candidate, pct=PROGRESS_PCT_SWITCH)

            fallback_config = replace(config, preset=candidate)
            try:
                fb_dom, fb_decision, fb_violations = self.attempt_runner.execute_attempt(
                    pdf_path, fallback_config, cand_score, cand_next_score, next_preset_id=following,
                )
            except Exception as exc:
                logger.warning("Fallback preset '%s' failed: %s", candidate, exc)
                if notifier is not None:
                    notifier.notify(PROGRESS_PCT_SWITCH, f"{candidate} failed, continuing", f"Fallback '{candidate}' failed ({exc}); skipping.")
                fail_dec: Dict[str, Any] = {"chosen_preset": candidate, "status": "ERROR", "overall_confidence": 0.0, "is_accepted": False}
                attempts.append(dict(self.attempt_runner.make_attempt_record(
                    len(attempts) + 1, candidate, fail_dec, [], action=ACTION_PATH_A_SWITCH,
                    reason=f"Fallback preset '{candidate}' failed: {exc}", detail=plan_note,
                )))
                continue

            fb_decision["decision_tree"] = {
                "action": ACTION_PATH_A_SWITCH,
                "preset_executed": candidate,
                "fallback_triggered": True,
                "reason": f"Previous preset fell below threshold ({prev_conf:.4f} < {config.target_threshold}). {plan_note}",
                "plan_status": "in_plan" if in_plan else "dynamic_fallback",
                "detail": plan_note,
            }
            attempts.append(dict(self.attempt_runner.make_attempt_record(
                len(attempts) + 1, candidate, fb_decision, fb_violations,
                action=ACTION_PATH_A_SWITCH, reason=fb_decision["decision_tree"]["reason"], detail=plan_note,
            )))
            fb_conf = _confidence_or_zero(fb_decision)
            if fb_decision.get("is_accepted") or fb_conf > best_conf:
                best_dom, best_decision, best_violations = fb_dom, fb_decision, fb_violations
                best_conf = fb_conf
            prev_conf = fb_conf
            curr_preset = candidate

        return best_dom, best_decision, best_violations

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
