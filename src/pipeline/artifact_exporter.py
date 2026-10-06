"""
src/pipeline/artifact_exporter.py

Artifact export helpers for DocumentDOM, quality violations, execution plans, and visual viewers.
"""

import os
import json
from typing import Dict, Any, List, Tuple, Optional

from src.utils import mkdirs
from src.dom import DocumentDOM
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

    return dom_output_path, violations_output_path, plan_result_path
