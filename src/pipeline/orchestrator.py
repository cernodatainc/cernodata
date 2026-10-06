"""
src/pipeline/orchestrator.py

End-to-end pipeline runner orchestrating parsing, text skew alignment, quality evaluation, exports, and rendering.
Supports executing custom and planner-generated execution plans.
"""

from typing import Any, Callable, Dict, List, Optional, Union

from src.pipeline.artifact_pipeline import PipelineArtifactPipeline
from src.pipeline.attempt_runner import AttemptRunner
from src.pipeline.config_resolver import PipelineConfigResolver
from src.pipeline.decision_tree import DEFAULT_TARGET_CONFIDENCE_THRESHOLD
from src.pipeline.execution_models import PipelineExecutionResult
from src.pipeline.fallback_handler import FallbackLoopHandler
from src.pipeline.planner_models import DocumentPlan, IngestionConfig
from src.pipeline.progress_notifier import PipelineProgressNotifier
from src.utils import resolve_pdf_path

__all__ = [
    "PipelineOrchestrator",
    "run_pipeline",
]


class PipelineOrchestrator:
    """Coordinates end-to-end document extraction, fallback loops, and artifact generation."""

    def __init__(
        self,
        attempt_runner: Optional[AttemptRunner] = None,
        fallback_handler: Optional[FallbackLoopHandler] = None,
        artifact_pipeline: Optional[PipelineArtifactPipeline] = None,
    ) -> None:
        self.attempt_runner = attempt_runner or AttemptRunner()
        self.fallback_handler = fallback_handler or FallbackLoopHandler(self.attempt_runner)
        self.artifact_pipeline = artifact_pipeline or PipelineArtifactPipeline()

    def execute(
        self,
        pdf_path: str,
        config: IngestionConfig,
        plan: Optional[DocumentPlan] = None,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> PipelineExecutionResult:
        """Executes end-to-end extraction pipeline with concrete configuration and optional fallback orchestration."""
        notifier = PipelineProgressNotifier(progress_callback)
        resolved_path = resolve_pdf_path(pdf_path)
        notifier.notify_initiation(resolved_path, config.preset, config.language)

        pdf_path = resolved_path
        attempts: List[Dict[str, Any]] = []

        next_candidate, part_of_plan, curr_score, next_score = self.fallback_handler.resolve_candidate_scores(
            config=config,
            plan=plan,
        )

        # Step 1: Initial Parse with Primary Preset
        notifier.notify_preset_execution(config.preset)
        dom, decision, violations = self.attempt_runner.execute_attempt(
            pdf_path, config, curr_score, next_score
        )
        attempts.append(dict(self.attempt_runner.make_attempt_record(1, config.preset, decision, violations)))
        notifier.notify_verification()

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
            notifier=notifier,
        )

        decision["attempts"] = attempts

        # Step 3: Export artifacts and overlays
        notifier.notify_exporting_artifacts()
        result = self.artifact_pipeline.export_and_package(
            pdf_path=pdf_path,
            dom=dom,
            decision=decision,
            violations=violations,
            config=config,
            plan=plan,
        )

        status_str = str(decision.get("status", "ACCEPT"))
        score_val = float(decision.get("overall_confidence", 1.0) or 1.0)
        notifier.notify_complete(status_str, score_val, len(violations))

        return result

    def run(
        self,
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
        """Resolves inputs and executes pipeline."""
        resolved_path, cfg, plan_obj = PipelineConfigResolver.resolve_request(
            pdf_path=pdf_path,
            target_threshold=target_threshold,
            language=language,
            preset=preset,
            align_skew=align_skew,
            visualize=visualize,
            output_dir=output_dir,
            plan=plan,
            config=config,
        )
        return self.execute(
            pdf_path=resolved_path,
            config=cfg,
            plan=plan_obj,
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
    """Convenience functional entrypoint delegating to PipelineOrchestrator."""
    return PipelineOrchestrator().run(
        pdf_path=pdf_path,
        target_threshold=target_threshold,
        language=language,
        preset=preset,
        align_skew=align_skew,
        visualize=visualize,
        output_dir=output_dir,
        plan=plan,
        config=config,
        progress_callback=progress_callback,
    )
