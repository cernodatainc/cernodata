"""
src/pipeline/planner_server.py

Zero-dependency HTTP server for interactive in-browser data shape configuration.
Serves data_shape_config.html and accepts submitted execution plans via API endpoints.
"""

from __future__ import annotations

import os
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Optional, Any

from src.utils import mkdirs, find_available_port
from src.pipeline.planner_models import DocumentPlan, PlannerCriteria
from src.pipeline.planner_options import (
    DEFAULT_PRESET_WEIGHTS,
    TAXONOMY_OPTIONS,
    TARGET_OPTIONS,
    SECURITY_OPTIONS,
    WIZARD_DIMENSIONS,
)
from src.pipeline.server import send_json_response, read_json_payload


class DataShapeServer(HTTPServer):
    """Custom HTTPServer tracking submitted plan and shutdown synchronization."""
    planner: Any
    default_doc: Optional[str]
    default_lang: Optional[str]
    default_threshold: float
    output_dir: str
    submitted_plan: Optional[DocumentPlan] = None
    html_content: str = ""


class DataShapeHandler(SimpleHTTPRequestHandler):
    """Request handler serving the interactive HTML wizard and processing plan submission."""

    server: DataShapeServer

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html", "/data_shape_config.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.server.html_content.encode("utf-8"))
            return

        elif self.path == "/api/config":
            send_json_response(self, 200, {
                "default_doc": self.server.default_doc or "",
                "default_lang": self.server.default_lang or "",
                "default_threshold": self.server.default_threshold,
                "preset_weights": DEFAULT_PRESET_WEIGHTS,
                "dimensions": [
                    {
                        "key": d.key,
                        "title": d.title,
                        "description": d.description,
                        "options": d.options,
                        "default": d.default,
                    }
                    for d in WIZARD_DIMENSIONS
                ],
                "taxonomy_options": TAXONOMY_OPTIONS,
                "target_options": TARGET_OPTIONS,
                "security_options": SECURITY_OPTIONS,
            })
            return

        return super().do_GET()

    def do_POST(self) -> None:
        payload = read_json_payload(self)

        if self.path == "/api/calculate_scores":
            criteria = PlannerCriteria.from_dict(payload)
            scores = self.server.planner.calculate_scores(criteria=criteria)
            suggested = self.server.planner.suggest_preset_order(scores)

            send_json_response(self, 200, {
                "success": True,
                "scores": scores,
                "suggested_order": suggested,
            })
            return

        elif self.path == "/api/submit_plan":
            document_path = payload.get("document_path", "").strip()
            if not document_path and self.server.default_doc:
                document_path = self.server.default_doc

            criteria = PlannerCriteria.from_dict(payload)
            raw_lang = payload.get("language")
            language = raw_lang.strip() if (isinstance(raw_lang, str) and raw_lang.strip() and raw_lang.strip().lower() != "none") else None
            try:
                target_threshold = float(payload.get("target_threshold", 0.82))
            except (ValueError, TypeError):
                target_threshold = 0.82

            override_primary = payload.get("override_primary")
            override_order = payload.get("override_order")

            plan = self.server.planner.create_plan(
                document_path=document_path,
                criteria=criteria,
                language=language,
                target_threshold=target_threshold,
                override_primary=override_primary,
                override_order=override_order,
            )

            self.server.submitted_plan = plan

            # Save plan.json to output directory
            if self.server.output_dir:
                mkdirs(self.server.output_dir)
                plan_file = os.path.join(self.server.output_dir, "plan.json")
                plan.save(plan_file)
            else:
                plan_file = ""

            if plan_file:
                send_json_response(self, 200, {
                    "success": True,
                    "message": "Plan successfully configured and saved.",
                    "plan_path": plan_file,
                    "plan": plan.to_dict(),
                })
            else:
                send_json_response(self, 200, {
                    "success": True,
                    "message": "Plan successfully configured but not saved (no output directory).",
                    "plan": plan.to_dict(),
                })

            print(f"\n[SERVER API] Received plan configuration from browser (Document: '{document_path}', Primary: '{plan.primary_preset}').")
            if plan_file:
                print(f"[SERVER API] Plan saved to '{plan_file}'.")

            # Schedule clean server shutdown
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        self.send_error(404, "Endpoint not found")

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP access logs to keep terminal output clean."""
        return


def serve_data_shape_wizard(
    planner: Any,
    default_doc: Optional[str] = None,
    default_lang: Optional[str] = None,
    default_threshold: float = 0.82,
    output_dir: str = "output",
    port: int = 8000,
    open_browser: bool = True
) -> DocumentPlan:
    """
    Serves interactive HTML questionnaire in browser to configure data shape parameters.
    Blocks until user submits plan via browser, then shuts down and returns DocumentPlan.
    """
    actual_port = find_available_port(start_port=port)

    # Locate and read HTML template
    html_src_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "visualization", "data_shape_config.html")
    if os.path.exists(html_src_path):
        with open(html_src_path, "r", encoding="utf-8") as f:
            html_content = f.read()
    else:
        html_content = "<html><body><h1>cernodata Data Shape Planner</h1><p>Template missing.</p></body></html>"

    # Also export standalone copy to output directory
    mkdirs(output_dir)
    exported_html_path = os.path.join(output_dir, "data_shape_config.html")
    with open(exported_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    httpd = DataShapeServer(("127.0.0.1", actual_port), DataShapeHandler)
    httpd.planner = planner
    httpd.default_doc = default_doc
    httpd.default_lang = default_lang
    httpd.default_threshold = default_threshold
    httpd.output_dir = output_dir
    httpd.html_content = html_content

    url = f"http://127.0.0.1:{actual_port}/data_shape_config.html"

    print("=" * 68, flush=True)
    print("cernodata: Interactive Data Shape & Preset Planner", flush=True)
    print("=" * 68, flush=True)
    print(f"Serving data shape questionnaire at: {url}", flush=True)
    print("Awaiting configuration in browser... (Press Ctrl+C to abort)", flush=True)
    print("=" * 68, flush=True)

    if open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        print("\n[SERVER] Data shape session interrupted by user.")
        httpd.server_close()
        raise

    httpd.server_close()

    if httpd.submitted_plan is not None:
        return httpd.submitted_plan

    # Fallback if somehow exited without plan
    return planner.create_plan(
        document_path=default_doc or "",
        language=default_lang,
        target_threshold=default_threshold
    )
