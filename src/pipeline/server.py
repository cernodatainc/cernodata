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
from src.pipeline.orchestrator import run_pipeline


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
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/rerun":
            content_length = int(self.headers.get("Content-Length", 0))
            body_data = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body_data) if body_data else {}

            preset = payload.get("preset", "docling_deep")
            pdf_path = payload.get("pdf_path", self.pdf_path)
            language = payload.get("language", self.language)
            self.language = language

            print(f"\n[SERVER API] Triggering live pipeline rerun for preset: '{preset}' (PDF: {pdf_path}, Lang: {language})...")
            result = run_pipeline(pdf_path=pdf_path, preset=preset, language=language)

            response_data = {
                "success": True,
                "preset": preset,
                "language": language,
                "dom": result["dom"],
                "violations": result["violations"],
                "decision": result["decision"]
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
            return

        elif self.path == "/api/save_dom":
            content_length = int(self.headers.get("Content-Length", 0))
            body_data = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body_data) if body_data else {}

            dom_data = payload.get("dom")
            output_dir = payload.get("output_dir", "output")

            if not dom_data:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing dom payload"}).encode("utf-8"))
                return

            os.makedirs(output_dir, exist_ok=True)
            dom_file = os.path.join(output_dir, "document_dom.json")
            with open(dom_file, "w", encoding="utf-8") as f:
                json.dump(dom_data, f, indent=2)

            print(f"\n[SERVER API] Saved updated DocumentDOM to '{dom_file}' ({len(dom_data.get('nodes', []))} nodes).")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "path": dom_file}).encode("utf-8"))
            return

        self.send_error(404, "Endpoint not found")


def start_pipeline_server(pdf_path: str = "", language: str = "pl", port: int = 8000, open_browser: bool = True):
    """Starts local HTTP server and opens interactive viewer in default web browser."""
    PipelineViewerHandler.pdf_path = pdf_path
    PipelineViewerHandler.language = language

    server_address = ("", port)
    httpd = HTTPServer(server_address, PipelineViewerHandler)
    url = f"http://localhost:{port}/interactive_viewer.html"

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
