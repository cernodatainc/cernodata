"""
src/cli.py

CLI Argument Parser & Console Output Summary Formatter.
"""

import os
import sys
import argparse
from typing import Dict, Any
from src.pipeline.decision_tree import DEFAULT_TARGET_CONFIDENCE_THRESHOLD


def parse_args():
    parser = argparse.ArgumentParser(
        description="cernodata: Layout-Aware Ingestion, Text Skew Alignment & Visual Overlay Renderer."
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
        "--no-align-skew", action="store_true",
        help="Disable automatic local text alignment skew detection."
    )
    parser.add_argument(
        "--output-dir", "-o", type=str, default="output",
        help="Directory to store JSON DOM, violations report, and rendered overlay images (default: output)"
    )
    parser.add_argument(
        "--no-visuals", action="store_true", help="Disable visual bounding box overlay rendering."
    )
    return parser.parse_args()


def print_summary(result: Dict[str, Any]):
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
    if result.get("html_viewer_path"):
        print(f"Interactive HTML Web Viewer: {result['html_viewer_path']}")
