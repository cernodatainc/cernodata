"""
src/visualization/viewer/scripts.py

Client-side JavaScript runtime loader for interactive HTML visual flow explorer.
Loads script runtime from modular JS files by concern or viewer.js.
"""

import os
import json
from typing import List

_VIEWER_DIR = os.path.dirname(os.path.abspath(__file__))
_JS_DIR = os.path.join(_VIEWER_DIR, "js")

JS_MODULE_ORDER: List[str] = [
    "state.js",
    "controls.js",
    "overlay.js",
    "inspector_components.js",
    "inspector.js",
    "cutout.js",
    "decollide_components.js",
    "decollide.js",
    "violations.js",
    "api.js",
    "app.js",
]


def bundle_viewer_js() -> str:
    """Concatenates the modular client scripts by concern in dependency order."""
    parts: List[str] = []
    for mod_name in JS_MODULE_ORDER:
        mod_path = os.path.join(_JS_DIR, mod_name)
        if os.path.exists(mod_path):
            with open(mod_path, "r", encoding="utf-8") as f:
                parts.append(f"/* === Concern Module: {mod_name} === */\n" + f.read())
    return "\n\n".join(parts)


def get_viewer_js() -> str:
    """Returns client script content assembled from subdivided modular JS sources."""
    return bundle_viewer_js()


def build_viewer_script(
    dom_json: str,
    violations_json: str,
    decision_json: str,
    detected_langs_json: str,
    plan_json: str,
    pdf_source_file: str,
    active_lang: str
) -> str:
    """Constructs script tag with hydrated VIEWER_DATA and viewer.js payload."""
    js_content = get_viewer_js()
    return f"""
    <script>
        window.VIEWER_DATA = {{
            dom: {dom_json},
            violations: {violations_json},
            decision: {decision_json},
            detectedLanguages: {detected_langs_json},
            plan: {plan_json},
            pdfSourceFile: {json.dumps(pdf_source_file)},
            activeLanguage: {json.dumps(active_lang)}
        }};
    </script>
    <script>
        {js_content}
    </script>
    """
