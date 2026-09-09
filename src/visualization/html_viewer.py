"""
src/visualization/html_viewer.py

Interactive HTML Visual Flow App & Live Step-by-Step Preset Explorer.
Supports language autodetection display, overrides, selection-only bounding box resizing,
and flagging incorrect parsed text.
"""

import os
import json
from typing import Dict, Any, List, Optional

from src.dom import DocumentDOM
from src.visualization.viewer import page_to_base64, build_viewer_html

# Backwards compatibility re-exports
_page_to_base64 = page_to_base64


def generate_interactive_html(
    pdf_path: str,
    dom: DocumentDOM,
    decision: Dict[str, Any],
    violations: List[Dict[str, Any]],
    output_path: str = os.path.join("output", "interactive_viewer.html"),
    plan: Optional[Dict[str, Any]] = None
) -> str:
    """Generates a standalone, interactive HTML visual flow explorer file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img_data_uri = page_to_base64(pdf_path, page_index=0)

    dom_json = json.dumps(dom.to_dict())
    violations_json = json.dumps(violations)
    decision_json = json.dumps(decision)
    plan_json = json.dumps(plan) if plan else "null"

    detected_langs = decision.get("detected_languages", {})
    if not detected_langs and dom.total_pages:
        from src.quality.language import detect_document_languages
        detected_langs = detect_document_languages(dom)
    detected_langs_json = json.dumps(detected_langs)

    html_content = build_viewer_html(
        dom=dom,
        decision=decision,
        violations=violations,
        img_data_uri=img_data_uri,
        dom_json=dom_json,
        violations_json=violations_json,
        decision_json=decision_json,
        detected_langs_json=detected_langs_json,
        plan_json=plan_json,
        plan=plan
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return output_path
