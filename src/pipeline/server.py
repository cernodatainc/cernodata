"""
src/pipeline/server.py

Zero-dependency HTTP server & live pipeline hub for interactive web application.
Serves thin landing page with navigation to input selection, planning, watching progress,
and multi-preset comparison results. Serves clean viewer HTML and JS assets and hydrates
runtime data from backend /api/viewer_data endpoint instead of returning templated HTML.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import webbrowser
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Dict, Any, List, Optional, Mapping

logger = logging.getLogger("cernodata.server")

from src.utils import mkdirs, find_available_port, resolve_pdf_path
from src.parsers.section_ocr import parse_image_ocr, parse_section_from_pdf
from src.pipeline.planner_options import (
    DEFAULT_PRESET_WEIGHTS,
    TAXONOMY_OPTIONS,
    TARGET_OPTIONS,
    SECURITY_OPTIONS,
    WIZARD_DIMENSIONS,
)
from src.pipeline.planner_models import PlannerCriteria


def send_json_response(handler: SimpleHTTPRequestHandler, status_code: int, payload: Any) -> None:
    """Sends JSON response with Content-Type and Content-Length headers."""
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json_payload(handler: SimpleHTTPRequestHandler) -> Dict[str, Any]:
    """Reads and decodes JSON request payload from HTTP request body."""
    content_length = int(handler.headers.get("Content-Length", 0))
    if content_length <= 0:
        return {}
    try:
        body = handler.rfile.read(content_length).decode("utf-8")
        return json.loads(body) if body else {}
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning("Malformed JSON request payload received: %s", e)
        return {}


SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(SRC_DIR)


class PipelineViewerHandler(SimpleHTTPRequestHandler):
    """HTTP request handler serving landing page, viewer assets, hydration API, and execution endpoints."""

    pdf_path: str = ""
    language: str = "en"
    viewer_data: Optional[Dict[str, Any]] = None
    current_result: Optional[Dict[str, Any]] = None
    preset_attempts: List[Dict[str, Any]] = []
    progress_state: Dict[str, Any] = {
        "status": "idle",
        "progress": 0,
        "step_index": 0,
        "current_step": "Idle - ready to execute",
        "logs": ["[INIT] Server ready. Waiting to trigger pipeline."],
        "completed": False,
        "error": None,
    }

    @classmethod
    def get_available_documents(cls) -> List[str]:
        """Finds candidate PDF documents in repository."""
        docs: List[str] = []
        patterns = [
            os.path.join(REPO_ROOT, "src", "e2e", "*.pdf"),
            os.path.join(REPO_ROOT, "output", "*.pdf"),
            os.path.join(REPO_ROOT, "*.pdf"),
            os.path.join(SRC_DIR, "e2e", "*.pdf"),
        ]
        for pattern in patterns:
            for match in glob.glob(pattern):
                try:
                    rel = os.path.relpath(match, REPO_ROOT).replace("\\", "/")
                except Exception:
                    rel = match.replace("\\", "/")
                if rel not in docs:
                    docs.append(rel)
        if not docs and cls.pdf_path:
            docs.append(cls.pdf_path)
        return docs

    @classmethod
    def get_viewer_data(cls) -> Dict[str, Any]:
        """Returns structured data required to hydrate the interactive visual viewer."""
        if cls.viewer_data is not None:
            return cls.viewer_data

        dom_file = os.path.join(REPO_ROOT, "output", "document_dom.json")
        viol_file = os.path.join(REPO_ROOT, "output", "quality_violations.json")
        dec_file = os.path.join(REPO_ROOT, "output", "decision_tree.json")
        plan_file = os.path.join(REPO_ROOT, "output", "plan.json")

        dom_data: Dict[str, Any] = {
            "document_id": "doc_init",
            "source_filename": cls.pdf_path or "Document 8.pdf",
            "total_pages": 1,
            "nodes": []
        }
        violations_data: List[Dict[str, Any]] = []
        decision_data: Dict[str, Any] = {
            "chosen_preset": "docling_fast",
            "overall_confidence": 1.0,
            "status": "ACCEPT",
            "attempts": cls.preset_attempts
        }
        plan_data: Optional[Dict[str, Any]] = None

        if os.path.exists(dom_file):
            try:
                with open(dom_file, "r", encoding="utf-8") as f:
                    dom_data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Could not load DOM cache from %s: %s", dom_file, e)

        if os.path.exists(viol_file):
            try:
                with open(viol_file, "r", encoding="utf-8") as f:
                    violations_data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Could not load violations cache from %s: %s", viol_file, e)

        if os.path.exists(dec_file):
            try:
                with open(dec_file, "r", encoding="utf-8") as f:
                    decision_data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Could not load decision cache from %s: %s", dec_file, e)

        if os.path.exists(plan_file):
            try:
                with open(plan_file, "r", encoding="utf-8") as f:
                    plan_data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Could not load plan cache from %s: %s", plan_file, e)

        raw_pdf = cls.pdf_path or dom_data.get("source_filename") or "src/e2e/Document 8.pdf"
        pdf_path = resolve_pdf_path(raw_pdf)
        total_pages = dom_data.get("total_pages", 1) or 1

        from src.visualization.viewer.pdf_renderer import render_all_pages_to_base64, get_pdf_page_dimensions
        page_images: List[str] = []
        page_dimensions: List[Dict[str, float]] = []

        if os.path.exists(pdf_path):
            try:
                page_images = render_all_pages_to_base64(pdf_path, total_pages=total_pages)
                page_dimensions = get_pdf_page_dimensions(pdf_path)
            except Exception as e:
                logger.warning("Could not render page images for %s: %s", pdf_path, e)

        cls.viewer_data = {
            "dom": dom_data,
            "violations": violations_data,
            "decision": decision_data,
            "detectedLanguages": decision_data.get("detected_languages", {}),
            "plan": plan_data,
            "pdfSourceFile": pdf_path,
            "activeLanguage": cls.language,
            "pageImages": page_images,
            "pageDimensions": page_dimensions,
            "totalPages": total_pages,
        }
        return cls.viewer_data

    @classmethod
    def update_result_state(cls, result: Mapping[str, Any], pdf_path: str, language: str) -> None:
        """Updates server memory state and hydration dataset from run_pipeline result."""
        resolved_path = resolve_pdf_path(pdf_path)
        cls.current_result = dict(result)
        cls.pdf_path = resolved_path
        cls.language = language

        dom_dict = result["dom"]
        decision_dict = result["decision"]
        violations_list = result["violations"]
        total_pages = dom_dict.get("total_pages", 1) or 1

        from src.visualization.viewer.pdf_renderer import render_all_pages_to_base64, get_pdf_page_dimensions
        page_images: List[str] = []
        page_dimensions: List[Dict[str, float]] = []

        if os.path.exists(pdf_path):
            try:
                page_images = render_all_pages_to_base64(pdf_path, total_pages=total_pages)
                page_dimensions = get_pdf_page_dimensions(pdf_path)
            except Exception as e:
                logger.warning("Could not render page images for %s: %s", pdf_path, e)

        cls.viewer_data = {
            "dom": dom_dict,
            "violations": violations_list,
            "decision": decision_dict,
            "detectedLanguages": decision_dict.get("detected_languages", {}),
            "plan": result.get("plan"),
            "pdfSourceFile": pdf_path,
            "activeLanguage": language,
            "pageImages": page_images,
            "pageDimensions": page_dimensions,
            "totalPages": total_pages,
        }

        # Sync preset attempts
        attempts = decision_dict.get("attempts", [])
        if attempts:
            cls.preset_attempts = attempts
        else:
            preset_name = decision_dict.get("chosen_preset", "docling_fast")
            record = {
                "step": len(cls.preset_attempts) + 1,
                "preset": preset_name,
                "overall_confidence": decision_dict.get("overall_confidence", 1.0),
                "per_page_confidence": decision_dict.get("per_page_confidence", {}),
                "violations_count": len(violations_list),
                "status": decision_dict.get("status", "ACCEPT"),
                "is_accepted": decision_dict.get("is_accepted", True),
                "action": decision_dict.get("decision_tree", {}).get("action", "ACCEPT_PARSE"),
            }
            existing_idx = next((i for i, a in enumerate(cls.preset_attempts) if a.get("preset") == preset_name), -1)
            if existing_idx != -1:
                cls.preset_attempts[existing_idx] = record
            else:
                cls.preset_attempts.append(record)

    def do_GET(self) -> None:
        raw_path = self.path.split("?")[0]

        # 1. Landing Page
        if raw_path in ("", "/", "/index.html", "/landing", "/hub"):
            landing_path = os.path.join(SRC_DIR, "visualization", "landing.html")
            if os.path.exists(landing_path):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(landing_path, "rb") as f:
                    self.wfile.write(f.read())
                return
            self.send_error(500, "Landing page template not found")
            return

        # 2. Viewer HTML (un-templated, dynamically hydrated)
        elif raw_path in ("/viewer", "/viewer.html"):
            viewer_file = os.path.join(SRC_DIR, "visualization", "viewer", "viewer.html")
            if not os.path.exists(viewer_file):
                viewer_file = os.path.join(SRC_DIR, "visualization", "viewer", "template.html")
            if os.path.exists(viewer_file):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(viewer_file, "rb") as f:
                    self.wfile.write(f.read())
                return
            self.send_error(500, "Viewer template not found")
            return

        # 3. Interactive Viewer backwards compatibility
        elif raw_path == "/interactive_viewer.html":
            target_file = os.path.join(REPO_ROOT, "output", "interactive_viewer.html")
            if os.path.exists(target_file):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(target_file, "rb") as f:
                    self.wfile.write(f.read())
                return
            viewer_file = os.path.join(SRC_DIR, "visualization", "viewer", "viewer.html")
            if os.path.exists(viewer_file):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(viewer_file, "rb") as f:
                    self.wfile.write(f.read())
                return
            self.send_error(404, "Interactive viewer not found")
            return

        # 4. Static CSS Asset
        elif raw_path == "/viewer.css":
            css_path = os.path.join(SRC_DIR, "visualization", "viewer", "viewer.css")
            if os.path.exists(css_path):
                self.send_response(200)
                self.send_header("Content-Type", "text/css; charset=utf-8")
                self.end_headers()
                with open(css_path, "rb") as f:
                    self.wfile.write(f.read())
                return
            self.send_error(404, "CSS asset not found")
            return

        # 5. Static JS Asset
        elif raw_path == "/viewer.js":
            js_path = os.path.join(SRC_DIR, "visualization", "viewer", "viewer.js")
            if os.path.exists(js_path):
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript; charset=utf-8")
                self.end_headers()
                with open(js_path, "rb") as f:
                    self.wfile.write(f.read())
                return
            self.send_error(404, "JavaScript asset not found")
            return

        # 6. Planner / Data Shape Questionnaire
        elif raw_path in ("/data_shape_config.html", "/data_shape", "/planner"):
            candidate_paths = [
                os.path.join(REPO_ROOT, "output", "data_shape_config.html"),
                os.path.join(SRC_DIR, "visualization", "data_shape_config.html")
            ]
            for target_file in candidate_paths:
                if os.path.exists(target_file):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    with open(target_file, "rb") as f:
                        self.wfile.write(f.read())
                    return
            self.send_error(404, "Planner page not found")
            return

        # 7. API Endpoints
        elif raw_path == "/api/config":
            send_json_response(self, 200, {
                "default_doc": self.pdf_path or "src/e2e/Document 8.pdf",
                "default_lang": self.language or "en",
                "default_threshold": 0.85,
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

        elif raw_path == "/api/documents":
            send_json_response(self, 200, {"documents": self.get_available_documents()})
            return

        elif raw_path == "/api/progress":
            send_json_response(self, 200, self.progress_state)
            return

        elif raw_path == "/api/results":
            send_json_response(self, 200, {
                "attempts": self.preset_attempts,
                "decision": self.current_result.get("decision") if self.current_result else None,
                "violations": self.current_result.get("violations") if self.current_result else [],
            })
            return

        elif raw_path == "/api/viewer_data":
            data = self.get_viewer_data()
            send_json_response(self, 200, data)
            return

        self.send_error(404, f"Endpoint not found: {raw_path}")

    def do_POST(self) -> None:
        payload = read_json_payload(self)
        timestamp = datetime.now().strftime("%H:%M:%S")

        if self.path == "/api/run":
            raw_pdf = payload.get("pdf_path", self.pdf_path) or "src/e2e/Document 8.pdf"
            pdf_path = resolve_pdf_path(raw_pdf)
            language = payload.get("language", self.language)
            threshold = float(payload.get("target_threshold", 0.85))
            preset = payload.get("preset", "docling_fast")
            align_skew = bool(payload.get("align_skew", True))
            visualize = bool(payload.get("visualize", True))
            with_plan = bool(payload.get("with_plan", False))
            plan_config = payload.get("plan_config")

            self.__class__.progress_state = {
                "status": "running",
                "progress": 20,
                "step_index": 1,
                "current_step": "Step 1: Document Validation & Subdivision",
                "logs": [
                    f"[{timestamp}] [START] Ingestion initiated for '{pdf_path}' (Preset: {preset}, Lang: {language}).",
                    f"[{timestamp}] [STEP 1] Validating document structure and parameters...",
                ],
                "completed": False,
                "error": None,
            }

            from src.pipeline.orchestrator import run_pipeline
            from src.pipeline.planner import PresetPlanner

            plan_obj = None
            if with_plan and plan_config:
                planner = PresetPlanner()
                criteria = PlannerCriteria(
                    taxonomy=plan_config.get("taxonomy", "standard"),
                    target=plan_config.get("target_use_case", "rag_vector_search"),
                    security=plan_config.get("security", "air_gapped_local"),
                )
                plan_obj = planner.create_plan(
                    document_path=pdf_path,
                    criteria=criteria,
                    language=language,
                    target_threshold=threshold,
                )

            self.__class__.progress_state["progress"] = 45
            self.__class__.progress_state["step_index"] = 2
            self.__class__.progress_state["current_step"] = f"Step 2: Executing Preset '{preset}'"
            self.__class__.progress_state["logs"].append(f"[{timestamp}] [STEP 2] Running layout extraction with preset '{preset}'...")

            try:
                result = run_pipeline(
                    pdf_path=pdf_path,
                    target_threshold=threshold,
                    language=language,
                    preset=preset,
                    align_skew=align_skew,
                    visualize=visualize,
                    plan=plan_obj
                )

                self.__class__.progress_state["progress"] = 80
                self.__class__.progress_state["step_index"] = 4
                self.__class__.progress_state["current_step"] = "Step 4: Quality Checks & Verification"
                self.__class__.progress_state["logs"].append(f"[{timestamp}] [STEP 4] Scanning DOM nodes for quality violations...")

                self.update_result_state(result, pdf_path=pdf_path, language=language)

                dec = result.get("decision", {})
                score = dec.get("overall_confidence", 1.0)
                status = dec.get("status", "ACCEPT")

                self.__class__.progress_state["progress"] = 100
                self.__class__.progress_state["step_index"] = 5
                self.__class__.progress_state["current_step"] = f"Step 5: Decision Tree Complete ({status})"
                self.__class__.progress_state["logs"].append(
                    f"[{timestamp}] [SUCCESS] Run complete: Status '{status}', Confidence: {score:.4f}, Violations: {len(result['violations'])}."
                )
                self.__class__.progress_state["status"] = "completed"
                self.__class__.progress_state["completed"] = True

                send_json_response(self, 200, {
                    "success": True,
                    "preset": preset,
                    "language": language,
                    "dom": result["dom"],
                    "violations": result["violations"],
                    "decision": result["decision"],
                    "plan": result.get("plan"),
                })
                return
            except Exception as e:
                self.__class__.progress_state["status"] = "error"
                self.__class__.progress_state["error"] = str(e)
                self.__class__.progress_state["logs"].append(f"[{timestamp}] [ERROR] Pipeline failure: {e}")
                send_json_response(self, 500, {"success": False, "error": str(e)})
                return

        elif self.path == "/api/rerun":
            preset = payload.get("preset", "docling_deep")
            raw_pdf = payload.get("pdf_path", self.pdf_path) or "src/e2e/Document 8.pdf"
            pdf_path = resolve_pdf_path(raw_pdf)
            language = payload.get("language", self.language)

            print(f"\n[SERVER API] Triggering live pipeline rerun for preset: '{preset}' (PDF: {pdf_path}, Lang: {language})...")
            from src.pipeline.orchestrator import run_pipeline
            result = run_pipeline(pdf_path=pdf_path, preset=preset, language=language)

            self.update_result_state(result, pdf_path=pdf_path, language=language)

            send_json_response(self, 200, {
                "success": True,
                "preset": preset,
                "language": language,
                "dom": result["dom"],
                "violations": result["violations"],
                "decision": result["decision"]
            })
            return

        elif self.path == "/api/calculate_scores":
            from src.pipeline.planner import PresetPlanner
            planner = PresetPlanner()
            criteria = PlannerCriteria.from_dict(payload)
            scores = planner.calculate_scores(criteria=criteria)
            suggested = planner.suggest_preset_order(scores)

            send_json_response(self, 200, {
                "success": True,
                "scores": scores,
                "suggested_order": suggested,
            })
            return

        elif self.path == "/api/submit_plan":
            from src.pipeline.planner_models import DocumentPlan
            plan = DocumentPlan.from_dict(payload)
            mkdirs("output")
            plan_path = os.path.join("output", "plan.json")
            plan.save(plan_path)
            send_json_response(self, 200, {"success": True, "plan_path": plan_path})
            return

        elif self.path == "/api/save_dom":
            dom_data = payload.get("dom")
            output_dir = payload.get("output_dir", "output")

            if not dom_data:
                send_json_response(self, 400, {"error": "Missing dom payload"})
                return

            mkdirs(output_dir)
            dom_file = os.path.join(output_dir, "document_dom.json")
            with open(dom_file, "w", encoding="utf-8") as f:
                json.dump(dom_data, f, indent=2)

            print(f"\n[SERVER API] Saved updated DocumentDOM to '{dom_file}' ({len(dom_data.get('nodes', []))} nodes).")
            send_json_response(self, 200, {"success": True, "path": dom_file})
            return

        elif self.path in ("/api/parse_section_ocr", "/api/ocr_section"):
            node_id = payload.get("node_id", "")
            image_base64 = payload.get("image_base64")
            bbox = payload.get("bbox")
            page = int(payload.get("page", 1))
            pdf_path = payload.get("pdf_path", self.pdf_path)
            language = payload.get("language", self.language)

            print(f"\n[SERVER API] Parsing selected section '{node_id}' using OCR (Lang: {language})...")

            ocr_result: Any
            if image_base64:
                ocr_result = parse_image_ocr(image_base64, language=language)
            elif pdf_path and bbox:
                ocr_result = parse_section_from_pdf(pdf_path, page, bbox, language=language)
            else:
                send_json_response(self, 400, {
                    "success": False,
                    "error": "Either image_base64 or (pdf_path and bbox) must be provided."
                })
                return

            response_data = {
                "success": ocr_result.get("success", False),
                "node_id": node_id,
                "text": ocr_result.get("text", ""),
                "confidence": ocr_result.get("confidence", 0.0),
                "lines": ocr_result.get("lines", []),
                "error": ocr_result.get("error")
            }
            send_json_response(self, 200 if response_data["success"] else 422, response_data)
            return

        self.send_error(404, "Endpoint not found")


def start_pipeline_server(
    pdf_path: str = "",
    language: str = "en",
    port: int = 8000,
    open_browser: bool = True
) -> None:
    """Starts local HTTP server and opens interactive hub landing page in default web browser."""
    actual_port = find_available_port(start_port=port)

    PipelineViewerHandler.pdf_path = pdf_path
    PipelineViewerHandler.language = language

    server_address = ("", actual_port)
    httpd = HTTPServer(server_address, PipelineViewerHandler)
    url = f"http://localhost:{actual_port}/"

    print("=" * 68)
    print(f"cernodata Ingestion Hub & Visual Server running at {url}")
    print(f"Dashboard Landing Page: {url}")
    print(f"Interactive Visual Flow Viewer: {url}viewer")
    print(f"Backend Hydration API: {url}api/viewer_data")
    print("=" * 68)

    if open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[SERVER] Stopping pipeline server.")
        httpd.server_close()


def main() -> None:
    """CLI entrypoint for standalone pipeline server."""
    import argparse

    parser = argparse.ArgumentParser(
        description="cernodata: Document Ingestion Hub, Preset Planner and Interactive Visual Viewer Server."
    )
    parser.add_argument("--pdf", "--input", "-i", type=str, default="", help="Path to initial PDF document")
    parser.add_argument("--language", "-l", type=str, default="en", help="Default language hint code (e.g. 'pl', 'en')")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch web browser")
    args = parser.parse_args()

    start_pipeline_server(
        pdf_path=args.pdf,
        language=args.language,
        port=args.port,
        open_browser=not args.no_browser,
    )


if __name__ == "__main__":
    main()
