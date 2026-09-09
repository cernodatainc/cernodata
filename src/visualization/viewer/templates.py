"""
src/visualization/viewer/templates.py

HTML template hydration and asset injection for the interactive visual flow explorer.
Loads HTML, CSS, and JS assets from disk and hydrates them with DocumentDOM runtime data.
"""

import os
import json
from typing import Dict, Any, List, Optional
from src.dom import DocumentDOM

_VIEWER_DIR = os.path.dirname(os.path.abspath(__file__))


def load_viewer_asset(filename: str) -> str:
    """Loads static text asset from the viewer directory."""
    path = os.path.join(_VIEWER_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def build_timeline_buttons(decision: Dict[str, Any], plan: Optional[Dict[str, Any]] = None) -> str:
    """Constructs HTML step buttons for preset candidate inspection and timeline toggles."""
    attempts = decision.get("attempts", [])
    if attempts and len(attempts) > 1:
        att1 = attempts[0]
        att2 = attempts[1]
        is_att1_pass = att1.get("is_accepted", False)
        is_att2_pass = att2.get("is_accepted", False)
        return f'''<button class="step-btn active" id="btnPreset1" onclick="switchPreset(0)">
                <span>Step 1: {att1.get("preset", "docling_fast")}</span>
                <span class="badge-status {"pass" if is_att1_pass else "fail"}" id="statusPreset1">{"ACCEPT" if is_att1_pass else "FALLBACK"}</span>
            </button>
            <button class="step-btn" id="btnPreset2" onclick="switchPreset(1)">
                <span>Step 2: {att2.get("preset", "docling_deep")}</span>
                <span class="badge-status {"pass" if is_att2_pass else "fail"}" id="statusPreset2">{"ACCEPT" if is_att2_pass else "FAIL"}</span>
            </button>'''

    is_acc = decision.get("is_accepted", True)
    chosen_preset = decision.get("chosen_preset", (plan.get("primary_preset") if plan else "docling_fast"))
    preset2_name = "docling_deep"
    if plan and plan.get("fallback_queue"):
        first_fb = plan["fallback_queue"][0]
        preset2_name = first_fb.get("preset", "docling_deep") if isinstance(first_fb, dict) else first_fb

    return f'''<button class="step-btn active" id="btnPreset1" onclick="switchPreset(0)">
                <span>Step 1: {chosen_preset}</span>
                <span class="badge-status {"pass" if is_acc else "fail"}" id="statusPreset1">{"ACCEPT" if is_acc else "REJECT"}</span>
            </button>
            <button class="step-btn fallback" id="btnPreset2" onclick="switchPreset(1)">
                <span>Step 2: {preset2_name}</span>
                <span class="badge-status" id="statusPreset2" style="background:#4B5563; color:#FFF;">Candidate</span>
            </button>'''


def build_viewer_html(
    dom: DocumentDOM,
    decision: Dict[str, Any],
    violations: List[Dict[str, Any]],
    img_data_uri: str,
    dom_json: str,
    violations_json: str,
    decision_json: str,
    detected_langs_json: str,
    plan_json: str,
    plan: Optional[Dict[str, Any]] = None
) -> str:
    """Assembles the interactive HTML application from template.html, viewer.css, and viewer.js."""
    template = load_viewer_asset("template.html")
    css_content = load_viewer_asset("viewer.css")
    js_content = load_viewer_asset("viewer.js")

    is_acc = decision.get("is_accepted", True)
    primary_detected = decision.get("primary_detected_language", "en")
    active_lang = decision.get("language", "pl")

    plan_header_sub = ""
    if plan:
        tax = plan.get("taxonomy", "standard")
        hw = plan.get("hardware", "cpu")
        is_over = plan.get("overridden", False)
        ov_text = " [OVERRIDDEN]" if is_over else ""
        plan_header_sub = f" | Plan: {tax} ({hw}){ov_text}"

    timeline_buttons = build_timeline_buttons(decision, plan)
    per_page = decision.get("per_page_confidence", {})
    p1_val = per_page.get("1") if "1" in per_page else per_page.get(1)
    if p1_val is None:
        p1_val = decision.get("overall_confidence", 1.0)
    page1_conf = f"{float(p1_val):.4f}"
    overall_conf = f"{float(decision.get('overall_confidence', 1.0)):.4f}"
    status_text = decision.get("status", "ACCEPT")

    replacements = {
        "<!-- __VIEWER_CSS__ -->": css_content,
        "<!-- __TIMELINE_BUTTONS__ -->": timeline_buttons,
        "{{ dom_source_filename }}": dom.source_filename,
        "{{ dom_document_id }}": dom.document_id,
        "{{ plan_header_sub }}": plan_header_sub,
        "{{ img_data_uri }}": img_data_uri,
        "{{ score_badge_classes }}": "" if is_acc else "fail",
        "{{ page1_confidence }}": page1_conf,
        "{{ overall_confidence }}": overall_conf,
        "{{ score_sub_color }}": "var(--accent-green)" if is_acc else "var(--accent-red)",
        "{{ decision_status }}": status_text,
        "{{ violations_count }}": str(len(violations)),
        "{{ dom_node_count }}": str(len(dom.nodes)),
        "{{ primary_detected }}": primary_detected,
        "{{ pl_selected }}": 'selected' if active_lang == 'pl' else '',
        "{{ en_selected }}": 'selected' if active_lang == 'en' else '',
        "{{ de_selected }}": 'selected' if active_lang == 'de' else '',
        "{{ fr_selected }}": 'selected' if active_lang == 'fr' else '',
        "{{ es_selected }}": 'selected' if active_lang == 'es' else '',
        "<!-- __DOM_JSON__ -->": dom_json,
        "<!-- __VIOLATIONS_JSON__ -->": violations_json,
        "<!-- __DECISION_JSON__ -->": decision_json,
        "<!-- __DETECTED_LANGS_JSON__ -->": detected_langs_json,
        "<!-- __PLAN_JSON__ -->": plan_json,
        "<!-- __PDF_SOURCE_FILE__ -->": json.dumps(dom.source_filename),
        "<!-- __ACTIVE_LANG__ -->": json.dumps(active_lang),
        "<!-- __VIEWER_JS__ -->": js_content,
    }

    result = template
    for placeholder, val in replacements.items():
        result = result.replace(placeholder, val)

    return result
