"""
src/pipeline/config_resolver.py

Input resolution and normalization for pipeline execution requests.
"""

from typing import Any, Dict, Optional, Tuple, Union

from src.pipeline.decision_tree import DEFAULT_TARGET_CONFIDENCE_THRESHOLD
from src.pipeline.planner.models import DocumentPlan, IngestionConfig


class PipelineConfigResolver:
    """Resolves flexible ingress arguments into strongly-typed execution inputs."""

    @staticmethod
    def resolve_plan(plan: Optional[Union[str, Dict[str, Any], DocumentPlan]]) -> Optional[DocumentPlan]:
        """Resolves raw plan input into a DocumentPlan instance."""
        if plan is None:
            return None
        if isinstance(plan, str):
            return DocumentPlan.load(plan)
        if isinstance(plan, dict):
            return DocumentPlan.from_dict(plan)
        if isinstance(plan, DocumentPlan):
            return plan
        return None

    @classmethod
    def resolve_config(
        cls,
        config: Optional[IngestionConfig] = None,
        plan_obj: Optional[DocumentPlan] = None,
        target_threshold: float = DEFAULT_TARGET_CONFIDENCE_THRESHOLD,
        language: Optional[str] = "en",
        preset: str = "docling_fast",
        align_skew: bool = True,
        visualize: bool = True,
        output_dir: str = "output",
    ) -> IngestionConfig:
        """Resolves concrete IngestionConfig from explicit config, plan, or parameters."""
        if config is not None:
            return config
        if plan_obj is not None:
            return plan_obj.to_ingestion_config(
                align_skew=align_skew,
                visualize=visualize,
                output_dir=output_dir,
            )
        return IngestionConfig(
            target_threshold=target_threshold,
            language=language,
            preset=preset,
            align_skew=align_skew,
            visualize=visualize,
            output_dir=output_dir,
        )

    @classmethod
    def resolve_request(
        cls,
        pdf_path: Optional[str] = None,
        target_threshold: float = DEFAULT_TARGET_CONFIDENCE_THRESHOLD,
        language: Optional[str] = "en",
        preset: str = "docling_fast",
        align_skew: bool = True,
        visualize: bool = True,
        output_dir: str = "output",
        plan: Optional[Union[str, Dict[str, Any], DocumentPlan]] = None,
        config: Optional[IngestionConfig] = None,
    ) -> Tuple[str, IngestionConfig, Optional[DocumentPlan]]:
        """Resolves target PDF path, IngestionConfig, and DocumentPlan."""
        plan_obj = cls.resolve_plan(plan)
        cfg = cls.resolve_config(
            config=config,
            plan_obj=plan_obj,
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
        return resolved_path, cfg, plan_obj
