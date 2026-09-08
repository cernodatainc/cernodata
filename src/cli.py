"""
src/cli.py

CLI Argument Parser & Console Output Summary Formatter.
Supports direct pipeline runs, interactive plan generation, and plan-driven execution.
"""

import os
import sys
import argparse
from typing import Dict, Any
from src.pipeline.decision_tree import DEFAULT_TARGET_CONFIDENCE_THRESHOLD


def parse_args():
    parser = argparse.ArgumentParser(
        description="cernodata: Layout-Aware Ingestion, Plan Wizard, Text Skew Alignment & Visual Overlay Renderer."
    )
    parser.add_argument(
        "--input", "-i", type=str, default=None,
        help="Path to input PDF file"
    )
    parser.add_argument(
        "--plan", "-p", type=str, default=None,
        help="Path to execution plan JSON file (e.g. output/plan.json)"
    )
    parser.add_argument(
        "--create-plan", action="store_true",
        help="Launch interactive planner questionnaire to configure preset ranking and execution plan."
    )
    parser.add_argument(
        "--plan-only", action="store_true",
        help="Generate and save execution plan without immediately running the pipeline."
    )
    parser.add_argument(
        "--override-preset", type=str, default=None,
        help="Explicitly override primary preset (e.g. 'docling_deep', 'docling_fast', 'vision_llm_direct')"
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
        "--diacritic-hit", type=float, default=None,
        help="Configurable score penalty hit for diacritic anomalies and conflicts (default from language config: 0.20)"
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
    parser.add_argument(
        "--serve", "-s", action="store_true",
        help="Start live HTTP server listening at http://localhost:8000 for backend pipeline rerun requests."
    )
    parser.add_argument(
        "--view", "-v", action="store_true",
        help="Automatically open the interactive HTML web viewer in the default browser."
    )
    return parser.parse_args()


def print_summary(result: Dict[str, Any]):
    decision = result["decision"]
    dom_dict = result["dom"]
    violations = result["violations"]
    plan = result.get("plan")

    print("\n--- Pipeline Summary ---")
    if plan:
        print("[Plan Context]")
        print(f"  Taxonomy: {plan.get('taxonomy')} | Hardware: {plan.get('hardware')}")
        print(f"  Primary Preset: {plan.get('primary_preset')} (Overridden: {plan.get('overridden')})")
        fb_names = [f.get('preset') if isinstance(f, dict) else str(f) for f in plan.get('fallback_queue', [])]
        print(f"  Fallback Queue: {', '.join(fb_names) if fb_names else 'None'}")
        print("-" * 25)

    print(f"Document ID: {dom_dict['document_id']}")
    print(f"Total Pages: {dom_dict['total_pages']}")
    print(f"Language Hint: {decision.get('language')}")
    print(f"Preset Executed: {decision.get('chosen_preset')}")
    print(f"Total DOM Nodes Extracted: {len(dom_dict['nodes'])}")
    print(f"Quality Violations Detected: {len(violations)}")
    print(f"Overall Confidence Score: {decision['overall_confidence']}")
    print(f"Decision Status: {decision['status']}")
    print(f"Action: {decision['decision_tree']['action']}")
    print(f"Reason: {decision['decision_tree']['reason']}")

    attempts = decision.get("attempts", [])
    if len(attempts) > 1:
        print("\n--- Pipeline Execution Attempts ---")
        for att in attempts:
            detail_str = f" | {att['detail']}" if att.get("detail") else ""
            print(
                f" [Step {att['step']}] Preset: {att['preset']} | Confidence: {att['overall_confidence']} "
                f"| Status: {att['status']}{detail_str}"
            )

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
    if result.get("plan_result_path"):
        print(f"Plan Execution Result exported to: {result['plan_result_path']}")
    if result.get("html_viewer_path"):
        print(f"Interactive HTML Web Viewer: {result['html_viewer_path']}")
