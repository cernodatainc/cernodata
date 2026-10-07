"""
src/pipeline/artifact_pipeline.py

Coordination of artifact generation, viewer export, and execution result packaging.
"""

from typing import Any, Dict, List, Optional

from src.dom import DocumentDOM
from src.pipeline.artifact_exporter import (
    export_interactive_html_viewer,
    export_pipeline_artifacts,
    render_visual_overlays,
)
from src.pipeline.execution_models import PipelineExecutionResult
from src.pipeline.planner.models import DocumentPlan, IngestionConfig


class PipelineArtifactPipeline:
    """Manages rendering, artifact exporting, and result packaging for pipeline extraction runs."""

    def export_and_package(
        self,
        pdf_path: str,
        dom: DocumentDOM,
        decision: Dict[str, Any],
        violations: List[Dict[str, Any]],
        config: IngestionConfig,
        plan: Optional[DocumentPlan] = None,
        render_overlays_fn: Any = render_visual_overlays,
        export_artifacts_fn: Any = export_pipeline_artifacts,
        export_viewer_fn: Any = export_interactive_html_viewer,
    ) -> PipelineExecutionResult:
        """Renders visual overlays, writes output JSON files, and packages result dictionary."""
        plan_dict = plan.to_dict() if plan else None
        rendered_images = render_overlays_fn(
            pdf_path, dom, violations, config.visualize, config.output_dir, decision=decision
        )
        dom_json_path, violations_json_path, plan_result_path = export_artifacts_fn(
            dom, decision, violations, config.language, config.output_dir, plan=plan_dict
        )
        html_viewer_path = export_viewer_fn(
            pdf_path, dom, decision, violations, config.output_dir, plan=plan_dict
        )

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
