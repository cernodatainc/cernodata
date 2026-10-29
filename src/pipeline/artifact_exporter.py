"""
src/pipeline/artifact_exporter.py

Artifact export helpers for DocumentDOM, quality violations, execution plans, and visual viewers.
"""

import os
import json
from typing import Dict, Any, List, Tuple, Optional

from src.utils import mkdirs
from src.dom import DocumentDOM
from src.quality.layers import normalize_layers
from src.quality.materialization import MaterializedVerificationResult
from src.visualization import PageVisualizer, generate_interactive_html


def render_visual_overlays(
    pdf_path: str,
    dom: DocumentDOM,
    violations: List[Dict[str, Any]],
    visualize: bool,
    output_dir: str,
    decision: Optional[Dict[str, Any]] = None
) -> List[str]:
    """Renders page visual overlay images with bounding boxes and violation markers if visualize is True."""
    if not visualize:
        return []
    visualizer = PageVisualizer()
    return visualizer.render_overlay(pdf_path, dom, violations=violations, output_dir=output_dir, decision=decision)


def export_interactive_html_viewer(
    pdf_path: str,
    dom: DocumentDOM,
    decision: Dict[str, Any],
    violations: List[Dict[str, Any]],
    output_dir: str,
    plan: Optional[Dict[str, Any]] = None
) -> str:
    """Generates self-contained interactive HTML web viewer file."""
    html_path = os.path.join(output_dir, "interactive_viewer.html")
    return generate_interactive_html(pdf_path, dom, decision, violations, output_path=html_path, plan=plan)


def export_rag_chunks_artifact(dom: DocumentDOM, output_dir: str) -> Optional[str]:
    """No-op hook for exporting hierarchical RAG JSONL chunks."""
    # TODO(TASK-302): Export hierarchical RAG chunks JSONL (`export_rag_jsonl`) with parent header breadcrumbs.
    _ = (dom, output_dir)
    return None


def export_markdown_and_sft_artifacts(dom: DocumentDOM, output_dir: str) -> Optional[str]:
    """No-op hook for exporting conversational Markdown and SFT pretraining JSONL."""
    # TODO(TASK-303): Export clean conversational Markdown and high-hygiene SFT pretraining JSONL (`min_confidence >= 0.85`).
    _ = (dom, output_dir)
    return None


def deliver_artifacts_to_sink(
    dom: DocumentDOM, target_uri: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """No-op hook for delivering formatted output payloads to an HTTP webhook or local URI sink."""
    # TODO(TASK-304): Deliver formatted payload to `pipe_target_uri` (`http://`, `https://`, or `file://`) when configured.
    _ = (dom, target_uri)
    return None


def build_downstream_recommendation(
    dom: DocumentDOM, plan: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """No-op hook for generating downstream chunking and tool recommendations by use case."""
    # TODO(TASK-305): Attach `recommend_downstream_setup(dom, use_case)` advisor summary to `execution_report`.
    _ = (dom, plan)
    return {}


def export_standalone_runner_script(
    output_dir: str, plan: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """No-op hook for emitting an audit-friendly standalone Python runner script."""
    # TODO(TASK-1001): Optionally emit a standalone, audit-friendly Python runner script (`generate_standalone_script`).
    _ = (output_dir, plan)
    return None


def export_pipeline_artifacts(
    dom: DocumentDOM,
    decision: Dict[str, Any],
    violations: List[Dict[str, Any]],
    language: Optional[str],
    output_dir: str,
    plan: Optional[Dict[str, Any]] = None
) -> Tuple[str, str, Optional[str]]:
    """Exports DocumentDOM JSON, standalone quality_violations.json, and plan_execution_result.json reports."""
    mkdirs(output_dir)
    export_rag_chunks_artifact(dom, output_dir)
    export_markdown_and_sft_artifacts(dom, output_dir)
    deliver_artifacts_to_sink(dom)
    build_downstream_recommendation(dom, plan)
    export_standalone_runner_script(output_dir, plan)

    dom_output_path = os.path.join(output_dir, "document_dom.json")
    with open(dom_output_path, "w", encoding="utf-8") as f:
        json.dump(dom.to_dict(), f, indent=2)

    violations_output_path = os.path.join(output_dir, "quality_violations.json")
    violations_report = {
        "document_id": dom.document_id,
        "source_filename": dom.source_filename,
        "language": language or "en",
        "detected_languages": decision.get("detected_languages", {}),
        "primary_detected_language": decision.get("primary_detected_language", "en"),
        "total_violations": len(violations),
        "violations": violations
    }
    with open(violations_output_path, "w", encoding="utf-8") as f:
        json.dump(violations_report, f, indent=2)

    # Always persist execution result and decision tree to avoid stale run artifacts
    plan_result_path = os.path.join(output_dir, "plan_execution_result.json")
    execution_report = {
        "plan": plan,
        "decision": decision,
        "total_violations": len(violations),
        "chosen_preset": decision.get("chosen_preset"),
        "status": decision.get("status"),
    }
    with open(plan_result_path, "w", encoding="utf-8") as f:
        json.dump(execution_report, f, indent=2)

    decision_tree_path = os.path.join(output_dir, "decision_tree.json")
    with open(decision_tree_path, "w", encoding="utf-8") as f:
        json.dump(decision, f, indent=2)

    # Materialize verification result artifact
    raw_layers = decision.get("selected_layers") or (plan.get("verification_layers") if plan else None)
    active_layers = [str(x) for x in raw_layers] if raw_layers is not None else normalize_layers(None)

    verif_res = MaterializedVerificationResult.from_decision(
        dom=dom,
        decision=decision,
        violations=violations,
        active_layers=active_layers,
        output_dir=output_dir,
    )
    verif_res.save(output_dir)

    return dom_output_path, violations_output_path, plan_result_path
