"""
src/pipeline/server.py

Zero-dependency HTTP server & live pipeline rerun API endpoint for interactive web app.
Serves interactive_viewer.html and executes live run_pipeline calls when user triggers preset reruns.
"""

import os
import json
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Dict, Any
from src.parsers.section_ocr import parse_image_ocr, parse_section_from_pdf


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
    except Exception:
        return {}


class PipelineViewerHandler(SimpleHTTPRequestHandler):
    pdf_path: str = ""
    language: str = "pl"

    def do_GET(self):
        if self.path in ("/", "/index.html", "/interactive_viewer.html"):
            target_file = os.path.join("output", "interactive_viewer.html")
            if os.path.exists(target_file):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(target_file, "rb") as f:
                    self.wfile.write(f.read())
                return
        elif self.path in ("/data_shape_config.html", "/data_shape", "/planner"):
            candidate_paths = [
                os.path.join("output", "data_shape_config.html"),
                os.path.join("src", "visualization", "data_shape_config.html")
            ]
            for target_file in candidate_paths:
                if os.path.exists(target_file):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    with open(target_file, "rb") as f:
                        self.wfile.write(f.read())
                    return
        return super().do_GET()

    def do_POST(self):
        payload = read_json_payload(self)

        if self.path == "/api/rerun":
            preset = payload.get("preset", "docling_deep")
            pdf_path = payload.get("pdf_path", self.pdf_path)
            language = payload.get("language", self.language)
            self.language = language

            print(f"\n[SERVER API] Triggering live pipeline rerun for preset: '{preset}' (PDF: {pdf_path}, Lang: {language})...")
            from src.pipeline.orchestrator import run_pipeline
            result = run_pipeline(pdf_path=pdf_path, preset=preset, language=language)

            send_json_response(self, 200, {
                "success": True,
                "preset": preset,
                "language": language,
                "dom": result["dom"],
                "violations": result["violations"],
                "decision": result["decision"]
            })
            return

        elif self.path == "/api/save_dom":
            dom_data = payload.get("dom")
            output_dir = payload.get("output_dir", "output")

            if not dom_data:
                send_json_response(self, 400, {"error": "Missing dom payload"})
                return

            os.makedirs(output_dir, exist_ok=True)
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

            result: Dict[str, Any]
            if image_base64:
                result = parse_image_ocr(image_base64, language=language)
            elif pdf_path and bbox:
                result = parse_section_from_pdf(pdf_path, page, bbox, language=language)
            else:
                send_json_response(self, 400, {
                    "success": False,
                    "error": "Either image_base64 or (pdf_path and bbox) must be provided."
                })
                return

            response_data = {
                "success": result.get("success", False),
                "node_id": node_id,
                "text": result.get("text", ""),
                "confidence": result.get("confidence", 0.0),
                "lines": result.get("lines", []),
                "error": result.get("error")
            }
            send_json_response(self, 200 if response_data["success"] else 422, response_data)
            return

        self.send_error(404, "Endpoint not found")


def start_pipeline_server(pdf_path: str = "", language: str = "pl", port: int = 8000, open_browser: bool = True):
    """Starts local HTTP server and opens interactive viewer in default web browser."""
    from src.pipeline.planner_server import find_available_port
    actual_port = find_available_port(start_port=port)

    PipelineViewerHandler.pdf_path = pdf_path
    PipelineViewerHandler.language = language

    server_address = ("", actual_port)
    httpd = HTTPServer(server_address, PipelineViewerHandler)
    url = f"http://localhost:{actual_port}/interactive_viewer.html"

    print("=" * 68)
    print(f"cernodata Interactive Live Pipeline Server running at {url}")
    print(f"Preset Rerun API endpoint listening at POST http://localhost:{port}/api/rerun")
    print("=" * 68)

    if open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[SERVER] Stopping live pipeline server.")
        httpd.server_close()
