"""
src/tests/test_pipeline_server.py

Unit and integration tests for the unified pipeline HTTP server (src/pipeline/server.py).
Tests:
- Thin landing page serving and section navigation
- Un-templated HTML viewer serving and static asset delivery (CSS, JS)
- Backend hydration via /api/viewer_data
- Real-time progress monitoring via /api/progress
- Preset comparison results via /api/results
- Document discovery via /api/documents
- Pipeline configuration and score calculation APIs
- DOM saving and updates via /api/save_dom
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import unittest
import urllib.request
import urllib.parse
from http.server import HTTPServer
from typing import Dict, Any

from src.pipeline.server import (
    PipelineViewerHandler,
    find_available_port,
    find_previous_runs,
)


class TestPipelineServer(unittest.TestCase):
    server: HTTPServer
    server_thread: threading.Thread
    port: int
    base_url: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.port = find_available_port(start_port=8900, max_attempts=50)
        cls.server = HTTPServer(("127.0.0.1", cls.port), PipelineViewerHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "server"):
            cls.server.shutdown()
            cls.server.server_close()

    def _get(self, path: str) -> tuple[int, str, Dict[str, str]]:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                status = response.status
                headers = dict(response.getheaders())
                content = response.read().decode("utf-8")
                return status, content, headers
        except urllib.error.HTTPError as e:
            content = e.read().decode("utf-8") if e.fp else ""
            return e.code, content, dict(e.headers)

    def _post_json(self, path: str, data: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                status = response.status
                res_body = response.read().decode("utf-8")
                parsed = json.loads(res_body) if res_body else {}
                return status, parsed
        except urllib.error.HTTPError as e:
            res_body = e.read().decode("utf-8") if e.fp else "{}"
            parsed = json.loads(res_body) if res_body else {}
            return e.code, parsed

    def test_landing_page_renders_four_navigation_sections(self) -> None:
        status, content, headers = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("Content-Type", ""))

        # Check strict emoji ban
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)
        self.assertFalse(bool(emoji_pattern.search(content)), "Emoji detected on landing page!")

        # Verify all four required navigation buttons and sections exist
        self.assertIn("tabBtnInput", content)
        self.assertIn("tabBtnPlan", content)
        self.assertIn("tabBtnProgress", content)
        self.assertIn("tabBtnResults", content)

        self.assertIn("secInput", content)
        self.assertIn("secPlan", content)
        self.assertIn("secProgress", content)
        self.assertIn("secResults", content)

        # Verify section titles and contents
        self.assertIn("Input Selection", content)
        self.assertIn("Planning", content)
        self.assertIn("Parsing Progress", content)
        self.assertIn("Preset Results", content)

    def test_viewer_html_endpoint_serves_untemplated_html(self) -> None:
        status, content, headers = self._get("/viewer")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("Content-Type", ""))

        # Verify links to static assets and absence of huge injected base64 blob
        self.assertIn("/viewer.css", content)
        self.assertIn("/viewer.js", content)
        self.assertIn("id=\"tabBtnDom\"", content)
        self.assertIn("id=\"tabBtnViol\"", content)
        self.assertIn("data-name=\"dom page\"", content)
        self.assertIn("data-name=\"violations\"", content)

    def test_static_css_and_js_served(self) -> None:
        # Test CSS
        status_css, content_css, headers_css = self._get("/viewer.css")
        self.assertEqual(status_css, 200)
        self.assertIn("text/css", headers_css.get("Content-Type", ""))
        self.assertIn(".merge-editor-card", content_css)

        # Test JS
        status_js, content_js, headers_js = self._get("/viewer.js")
        self.assertEqual(status_js, 200)
        self.assertIn("application/javascript", headers_js.get("Content-Type", ""))
        self.assertIn("hydrateViewer", content_js)
        self.assertIn("extractViolationsList", content_js)
        self.assertIn("executeMergeElements", content_js)
        self.assertIn("mergeDOMNodes", content_js)

        # Test landing CSS and JS
        status_l_css, content_l_css, headers_l_css = self._get("/landing.css")
        self.assertEqual(status_l_css, 200)
        self.assertIn("text/css", headers_l_css.get("Content-Type", ""))
        self.assertIn(".hub-nav-bar", content_l_css)

        status_l_js, content_l_js, headers_l_js = self._get("/landing.js")
        self.assertEqual(status_l_js, 200)
        self.assertIn("application/javascript", headers_l_js.get("Content-Type", ""))
        self.assertIn("switchNavTab", content_l_js)

        # Test data shape config CSS and JS
        status_ds_css, content_ds_css, headers_ds_css = self._get("/data_shape_config.css")
        self.assertEqual(status_ds_css, 200)
        self.assertIn("text/css", headers_ds_css.get("Content-Type", ""))
        self.assertIn(".main-container", content_ds_css)

        status_ds_js, content_ds_js, headers_ds_js = self._get("/data_shape_config.js")
        self.assertEqual(status_ds_js, 200)
        self.assertIn("application/javascript", headers_ds_js.get("Content-Type", ""))
        self.assertIn("PRESET_WEIGHTS", content_ds_js)

    def test_api_viewer_data_hydration(self) -> None:
        status, content, headers = self._get("/api/viewer_data")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("Content-Type", ""))
        data = json.loads(content)

        # Check required hydration payload structure
        self.assertIn("dom", data)
        self.assertIn("violations", data)
        self.assertIsInstance(data["violations"], list)
        self.assertIn("decision", data)
        self.assertIn("pageImages", data)
        self.assertIn("pageDimensions", data)

    def test_api_progress_endpoint(self) -> None:
        status, content, headers = self._get("/api/progress")
        self.assertEqual(status, 200)
        data = json.loads(content)
        self.assertIn("status", data)
        self.assertIn("progress", data)
        self.assertIn("step_index", data)
        self.assertIn("logs", data)

    def test_api_results_endpoint(self) -> None:
        status, content, headers = self._get("/api/results")
        self.assertEqual(status, 200)
        data = json.loads(content)
        self.assertIn("attempts", data)
        self.assertIn("decision", data)
        self.assertIn("violations", data)

    def test_api_documents_endpoint(self) -> None:
        status, content, headers = self._get("/api/documents")
        self.assertEqual(status, 200)
        data = json.loads(content)
        self.assertIn("documents", data)
        self.assertIsInstance(data["documents"], list)

    def test_api_config_endpoint(self) -> None:
        status, content, headers = self._get("/api/config")
        self.assertEqual(status, 200)
        data = json.loads(content)
        self.assertIn("default_doc", data)
        self.assertIn("default_lang", data)
        self.assertIn("preset_weights", data)
        self.assertIn("dimensions", data)

    def test_api_calculate_scores_endpoint(self) -> None:
        payload = {
            "document_path": "src/e2e/Document 8.pdf",
            "taxonomy": "standard",
            "target_use_case": "rag_vector_search",
            "latency": "balanced",
            "hardware": "cpu",
            "target_threshold": 0.85,
        }
        status, resp = self._post_json("/api/calculate_scores", payload)
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("success"))
        self.assertIn("scores", resp)
        self.assertIn("suggested_order", resp)

    def test_api_save_dom_endpoint(self) -> None:
        dom_payload = {
            "document_id": "test_save_doc",
            "source_filename": "test.pdf",
            "total_pages": 1,
            "nodes": [
                {
                    "node_id": "node_1",
                    "page_number": 1,
                    "type": "text",
                    "text": "Saved text",
                    "bbox": [10.0, 10.0, 100.0, 50.0],
                }
            ],
        }
        status, resp = self._post_json("/api/save_dom", {"dom": dom_payload, "output_dir": "test_output_save"})
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("success"))
        self.assertIn("path", resp)
        self.assertTrue(os.path.exists(resp["path"]))

        # Cleanup
        if os.path.exists("test_output_save"):
            import shutil
            shutil.rmtree("test_output_save", ignore_errors=True)

    def test_find_previous_runs_discovers_outputs(self) -> None:
        runs = find_previous_runs()
        self.assertIsInstance(runs, list)
        self.assertGreater(len(runs), 0)
        run_ids = [r["id"] for r in runs]
        # output or src/e2e/output should be found
        self.assertTrue(any("output" in rid for rid in run_ids))
        first_run = runs[0]
        self.assertIn("dir_path", first_run)
        self.assertIn("document_name", first_run)
        self.assertIn("chosen_preset", first_run)
        self.assertIn("status", first_run)
        self.assertIn("overall_confidence", first_run)
        self.assertIn("label", first_run)

    def test_api_previous_runs_endpoint(self) -> None:
        status, content, _ = self._get("/api/previous_runs")
        self.assertEqual(status, 200)
        data = json.loads(content)
        self.assertIn("runs", data)
        self.assertIn("active_run", data)
        self.assertIsInstance(data["runs"], list)
        self.assertGreater(len(data["runs"]), 0)

    def test_api_load_run_endpoint_post_and_get(self) -> None:
        # Test POST /api/load_run
        status, resp = self._post_json("/api/load_run", {"output_dir": "output"})
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("success"))
        self.assertEqual(resp.get("output_dir"), "output")
        self.assertIn("run", resp)
        self.assertIn("results", resp)

        # Test GET /api/load_run?output_dir=output
        status, content, _ = self._get("/api/load_run?output_dir=output")
        self.assertEqual(status, 200)
        get_data = json.loads(content)
        self.assertTrue(get_data.get("success"))
        self.assertEqual(get_data.get("output_dir"), "output")

    def test_api_results_and_viewer_data_with_output_dir(self) -> None:
        # Query results specifying output directory
        status, content, _ = self._get("/api/results?output_dir=output")
        self.assertEqual(status, 200)
        res_data = json.loads(content)
        self.assertIn("attempts", res_data)
        self.assertIn("decision", res_data)
        self.assertIn("output_dir", res_data)
        self.assertEqual(res_data["output_dir"], "output")

        # Query viewer_data specifying output directory
        status, content, _ = self._get("/api/viewer_data?output_dir=output")
        self.assertEqual(status, 200)
        v_data = json.loads(content)
        self.assertIn("dom", v_data)
        self.assertIn("violations", v_data)
        self.assertIsInstance(v_data["violations"], list)
        self.assertIn("decision", v_data)
        self.assertEqual(v_data.get("outputDir"), "output")
