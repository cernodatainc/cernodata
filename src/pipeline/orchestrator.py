"""
src/pipeline/orchestrator.py

End-to-end pipeline runner orchestrating parsing, text skew alignment, quality evaluation, exports, and rendering.
Composed of dedicated, single-responsibility step functions.
"""

import os
import json
from typing import Dict, Any, List, Tuple

from src.dom import DocumentDOM
from src.parsers import DoclingParser
from src.quality import detect_quality_violations, apply_text_skew_alignment
from src.pipeline.decision_tree import DecisionTreeEngine, DEFAULT_TARGET_CONFIDENCE_THRESHOLD
from src.visualization import PageVisualizer, generate_interactive_html


def parse_document(pdf_path: str, language: str) -> DocumentDOM:
    """Parses PDF document using Docling layout parser into DocumentDOM IR."""
    parser = DoclingParser(language=language)
    return parser.parse(pdf_path)


def align_document_skew(dom: DocumentDOM, pdf_path: str, align_skew: bool) -> DocumentDOM:
    """Auto-detects and applies local text line skew orientation angles per node."""
    if align_skew:
        return apply_text_skew_alignment(dom, pdf_path)
    return dom


def evaluate_quality_and_decision_tree(
    dom: DocumentDOM, target_threshold: float, language: str
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Extracts quality violation records and evaluates confidence scores against target threshold."""
    violations = detect_quality_violations(dom, language=language)
    engine = DecisionTreeEngine(target_threshold=target_threshold, language=language)
    decision = engine.evaluate(dom)
    return decision, violations


def render_visual_overlays(
    pdf_path: str, dom: DocumentDOM, violations: List[Dict[str, Any]], visualize: bool, output_dir: str
) -> List[str]:
    """Renders page visual overlay images with bounding boxes and violation markers if visualize is True."""
    if not visualize:
        return []
    visualizer = PageVisualizer()
    return visualizer.render_overlay(pdf_path, dom, violations=violations, output_dir=output_dir)


def export_interactive_html_viewer(
    pdf_path: str, dom: DocumentDOM, decision: Dict[str, Any], violations: List[Dict[str, Any]], output_dir: str
) -> str:
    """Generates self-contained interactive HTML web viewer file."""
    html_path = os.path.join(output_dir, "interactive_viewer.html")
    return generate_interactive_html(pdf_path, dom, decision, violations, output_path=html_path)


def export_pipeline_artifacts(
    dom: DocumentDOM, decision: Dict[str, Any], violations: List[Dict[str, Any]], language: str, output_dir: str
) -> Tuple[str, str]:
    """Exports DocumentDOM JSON and standalone quality_violations.json reports."""
    os.makedirs(output_dir, exist_ok=True)

    dom_output_path = os.path.join(output_dir, "document_dom.json")
    with open(dom_output_path, "w", encoding="utf-8") as f:
        json.dump(dom.to_dict(), f, indent=2)

    violations_output_path = os.path.join(output_dir, "quality_violations.json")
    violations_report = {
        "document_id": dom.document_id,
        "source_filename": dom.source_filename,
        "language": language,
        "total_violations": len(violations),
        "violations": violations
    }
    with open(violations_output_path, "w", encoding="utf-8") as f:
        json.dump(violations_report, f, indent=2)

    return dom_output_path, violations_output_path


def run_pipeline(
    pdf_path: str,
    target_threshold: float = DEFAULT_TARGET_CONFIDENCE_THRESHOLD,
    language: str = "en",
    align_skew: bool = True,
    visualize: bool = True,
    output_dir: str = "output"
) -> Dict[str, Any]:
    """Executes end-to-end extraction pipeline by composing dedicated step functions."""
    dom = parse_document(pdf_path, language)
    dom = align_document_skew(dom, pdf_path, align_skew)
    decision, violations = evaluate_quality_and_decision_tree(dom, target_threshold, language)
    rendered_images = render_visual_overlays(pdf_path, dom, violations, visualize, output_dir)
    dom_json_path, violations_json_path = export_pipeline_artifacts(dom, decision, violations, language, output_dir)
    html_viewer_path = export_interactive_html_viewer(pdf_path, dom, decision, violations, output_dir)

    return {
        "dom": dom.to_dict(),
        "decision": decision,
        "violations": violations,
        "dom_json_path": dom_json_path,
        "violations_json_path": violations_json_path,
        "html_viewer_path": html_viewer_path,
        "rendered_images": rendered_images
    }
