"""
src/pipeline/orchestrator.py

End-to-end pipeline runner orchestrating parsing, quality evaluation, exports, and rendering.
"""

import os
import json
from typing import Dict, Any

from src.parsers import DoclingParser
from src.quality import detect_quality_violations
from src.pipeline.decision_tree import DecisionTreeEngine, DEFAULT_TARGET_CONFIDENCE_THRESHOLD
from src.visualization import PageVisualizer


def run_pipeline(
    pdf_path: str,
    target_threshold: float = DEFAULT_TARGET_CONFIDENCE_THRESHOLD,
    language: str = "en",
    visualize: bool = True,
    output_dir: str = "output"
) -> Dict[str, Any]:
    """
    Executes end-to-end cernodata extraction pipeline:
    1. Parse PDF using Docling into DocumentDOM IR with language hinting.
    2. Detect specific quality violations & diacritic anomalies (e.g. 'piqtku' vs 'piątku').
    3. Run Tier 2 language quality decision tree heuristics and fallback evaluation.
    4. Export document_dom.json and standalone quality_violations.json.
    5. Render visual provenance overlay images with red violation markers & bottom-left score badge.
    """
    os.makedirs(output_dir, exist_ok=True)

    # 1. Parsing and DOM conversion
    parser = DoclingParser(language=language)
    dom = parser.parse(pdf_path)

    # 2. Quality Violations Extraction
    violations = detect_quality_violations(dom, language=language)

    # 3. Decision Tree Evaluation
    engine = DecisionTreeEngine(target_threshold=target_threshold, language=language)
    decision = engine.evaluate(dom)

    # 4. Visual Overlay Rendering
    rendered_images = []
    if visualize:
        visualizer = PageVisualizer()
        rendered_images = visualizer.render_overlay(
            pdf_path, dom, violations=violations, output_dir=output_dir
        )

    # Export DocumentDOM JSON
    dom_output_path = os.path.join(output_dir, "document_dom.json")
    with open(dom_output_path, "w", encoding="utf-8") as f:
        json.dump(dom.to_dict(), f, indent=2)

    # Export Standalone Quality Violations JSON
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

    return {
        "dom": dom.to_dict(),
        "decision": decision,
        "violations": violations,
        "dom_json_path": dom_output_path,
        "violations_json_path": violations_output_path,
        "rendered_images": rendered_images
    }
