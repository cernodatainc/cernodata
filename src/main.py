"""
src/main.py

Main CLI Entry Point for cernodata PDF layout parsing, language-aware quality decision tree evaluation,
quality violations detection, standalone JSON exporting, and page visual overlay rendering.
"""

import os
import sys
import json
import argparse
from typing import Dict, Any

# Ensure parent path is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.converter import DoclingParser
    from src.heuristics import detect_quality_violations
    from src.decision_tree import DecisionTreeEngine, DEFAULT_TARGET_CONFIDENCE_THRESHOLD
    from src.visualizer import PageVisualizer
except ImportError:
    from converter import DoclingParser
    from heuristics import detect_quality_violations
    from decision_tree import DecisionTreeEngine, DEFAULT_TARGET_CONFIDENCE_THRESHOLD
    from visualizer import PageVisualizer


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

    # 4. Visual Overlay Rendering with violation highlights & bottom-left score badge
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


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="cernodata: Layout-Aware Ingestion, Quality Violations Reporter & Visual Overlay Renderer."
    )
    parser.add_argument(
        "--input", "-i", type=str, default=os.path.join("src", "Document 5.pdf"),
        help="Path to input PDF file (default: src/Document 5.pdf)"
    )
    parser.add_argument(
        "--target-threshold", "-t", type=float, default=DEFAULT_TARGET_CONFIDENCE_THRESHOLD,
        help=f"Target confidence threshold (default: {DEFAULT_TARGET_CONFIDENCE_THRESHOLD})"
    )
    parser.add_argument(
        "--language", "-l", type=str, default="en",
        help="Language hint code for OCR and quality verification (e.g. 'pl' for Polish, 'de' for German, 'en' for English)"
    )
    parser.add_argument(
        "--output-dir", "-o", type=str, default="output",
        help="Directory to store JSON DOM, violations report, and rendered overlay images (default: output)"
    )
    parser.add_argument(
        "--no-visuals", action="store_true", help="Disable visual bounding box overlay rendering."
    )

    args = parser.parse_args()

    print("=" * 68)
    print("cernodata: Layout-Aware Ingestion & Quality Violations Pipeline")
    print("=" * 68)
    print(f"Input Document: {args.input}")
    print(f"Language Hint: {args.language}")
    print(f"Target Confidence Threshold: {args.target_threshold}")

    if not os.path.exists(args.input):
        print(f"[ERROR] Specified input file '{args.input}' does not exist.")
        sys.exit(1)

    result = run_pipeline(
        pdf_path=args.input,
        target_threshold=args.target_threshold,
        language=args.language,
        visualize=not args.no_visuals,
        output_dir=args.output_dir
    )

    decision = result["decision"]
    dom_dict = result["dom"]
    violations = result["violations"]

    print("\n--- Pipeline Summary ---")
    print(f"Document ID: {dom_dict['document_id']}")
    print(f"Total Pages: {dom_dict['total_pages']}")
    print(f"Language Hint: {decision['language']}")
    print(f"Total DOM Nodes Extracted: {len(dom_dict['nodes'])}")
    print(f"Quality Violations Detected: {len(violations)}")
    print(f"Overall Confidence Score: {decision['overall_confidence']}")
    print(f"Decision Status: {decision['status']}")
    print(f"Action: {decision['decision_tree']['action']}")
    print(f"Reason: {decision['decision_tree']['reason']}")

    if violations:
        print("\n--- Specific Quality Violations Detected ---")
        for v in violations:
            snip = v.get('detected_snippet')
            corr = v.get('suggested_correction', '')
            corr_str = f" -> '{corr}'" if corr else ""
            print(f" [!] Node {v['node_id']} ({v['rule_type']}): '{snip}'{corr_str}")

    if result["rendered_images"]:
        print("\n--- Page Overlay Images Rendered ---")
        for img_path in result["rendered_images"]:
            print(f" -> {img_path}")

    print(f"\nDocumentDOM JSON exported to: {result['dom_json_path']}")
    print(f"Quality Violations JSON exported to: {result['violations_json_path']}")


if __name__ == "__main__":
    main()
