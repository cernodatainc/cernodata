"""
src/cli.py

CLI Argument Parser & Console Output Summary Formatter.
Re-exports parser utilities from src.main and provides terminal summary formatting.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Mapping

from src.main import create_parser, parse_args

__all__ = [
    "create_parser",
    "parse_args",
    "print_summary",
]


def print_summary(result: Mapping[str, Any]) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception as ex:
            logging.getLogger("cernodata.cli").debug("Unable to reconfigure stdout encoding: %s", ex)

    decision = result["decision"]
    dom_dict = result["dom"]
    violations = result["violations"]
    plan = result.get("plan")

    print("\n--- Pipeline Summary ---")
    if plan:
        print("[Plan Context]")
        print(f"  Taxonomy: {plan.get('taxonomy')}")
        print(f"  Primary Preset: {plan.get('primary_preset')} (Overridden: {plan.get('overridden')})")
        fb_names = [str(f.get('preset', '')) if isinstance(f, dict) else str(f) for f in plan.get('fallback_queue', [])]
        fb_names = [n for n in fb_names if n]
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
