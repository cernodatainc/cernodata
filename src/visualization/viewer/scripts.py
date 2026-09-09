"""
src/visualization/viewer/scripts.py

Client-side JavaScript runtime loader for interactive HTML visual flow explorer.
Loads script runtime from viewer.js on demand.
"""

import os
import json

_JS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer.js")


def get_viewer_js() -> str:
    """Returns client script content from viewer.js."""
    with open(_JS_PATH, "r", encoding="utf-8") as f:
        return f.read()


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
