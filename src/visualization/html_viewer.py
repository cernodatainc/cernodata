"""
src/visualization/html_viewer.py

Interactive HTML Visual Flow App & Live Step-by-Step Preset Explorer.
Supports language autodetection display, overrides, selection-only bounding box resizing,
and flagging incorrect parsed text.
"""

import os
import json
from typing import Dict, Any, List, Optional, Union

from src.utils import mkdirs
from src.dom import DocumentDOM
from src.visualization.viewer import (
    page_to_base64,
    get_pdf_page_dimensions,
    render_all_pages_to_base64,
    build_viewer_html,
)

# Backwards compatibility re-exports
_page_to_base64 = page_to_base64


def generate_interactive_html(
    pdf_path: str,
    dom: DocumentDOM,
    decision: Dict[str, Any],
    violations: Union[List[Dict[str, Any]], Dict[str, Any]],
    output_path: str = os.path.join("output", "interactive_viewer.html"),
    plan: Optional[Dict[str, Any]] = None
) -> str:
    """Generates a standalone, interactive HTML visual flow explorer file."""
    mkdirs(os.path.dirname(output_path))
    total_pages = dom.total_pages if dom.total_pages and dom.total_pages > 0 else 1
    page_images = render_all_pages_to_base64(pdf_path, total_pages=total_pages)
    img_data_uri = page_images[0] if page_images else page_to_base64(pdf_path, page_index=0)
    page_dimensions = get_pdf_page_dimensions(pdf_path)

    if isinstance(violations, dict):
        violations_list = violations.get("violations", [])
    elif isinstance(violations, list):
        violations_list = violations
    else:
        violations_list = []

    dom_json = json.dumps(dom.to_dict())
    violations_json = json.dumps(violations_list)
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
        violations=violations_list,
        img_data_uri=img_data_uri,
        dom_json=dom_json,
        violations_json=violations_json,
        decision_json=decision_json,
        detected_langs_json=detected_langs_json,
        plan_json=plan_json,
        plan=plan,
        page_images=page_images,
        page_dimensions=page_dimensions,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return output_path
