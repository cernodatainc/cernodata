"""
src/tests/test_data_shape_server.py

Unit tests for interactive data shape HTML interface, planner server,
and browser questionnaire workflow.
"""

import os
import re
import json
import socket
import threading
import unittest
import urllib.request
import urllib.parse
from http.server import HTTPServer

from src.pipeline.planner import PresetPlanner, DocumentPlan
from src.pipeline.planner_server import (
    DataShapeServer,
    DataShapeHandler,
    find_available_port,
    serve_data_shape_wizard,
)


class TestDataShapeServer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.planner = PresetPlanner()
        cls.html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "visualization",
            "data_shape_config.html"
        )
        cls.test_output = "test_output_server"
        os.makedirs(cls.test_output, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        import shutil
        if os.path.exists(cls.test_output):
            shutil.rmtree(cls.test_output, ignore_errors=True)

    def test_html_template_exists_and_contains_required_fields(self):
        self.assertTrue(os.path.exists(self.html_path), "data_shape_config.html does not exist.")
        with open(self.html_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Strict Emoji Ban Check
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)
        self.assertFalse(bool(emoji_pattern.search(content)), "Emoji detected in data_shape_config.html!")

        # Verify key UI components exist
        self.assertIn("cernodata Data Shape & Preset Planner", content)
        self.assertIn("docPath", content)
        self.assertIn("langCode", content)
        self.assertIn("thresholdSlider", content)
        self.assertIn("taxonomyGrid", content)
        self.assertIn("hardwareGrid", content)
        self.assertIn("targetGrid", content)
        self.assertIn("securityGrid", content)
        self.assertIn("presetsList", content)
        self.assertIn("overrideSelect", content)
        self.assertIn("submitBtn", content)
        self.assertIn("/api/submit_plan", content)

    def test_find_available_port(self):
        port = find_available_port(start_port=8100, max_attempts=10)
        self.assertGreaterEqual(port, 8100)

    def test_server_endpoints(self):
        port = find_available_port(start_port=9200, max_attempts=20)
        httpd = DataShapeServer(("127.0.0.1", port), DataShapeHandler)
        httpd.planner = self.planner
        httpd.default_doc = "sample_test.pdf"
        httpd.default_lang = "pl"
        httpd.default_threshold = 0.85
        httpd.output_dir = self.test_output

        with open(self.html_path, "r", encoding="utf-8") as f:
            httpd.html_content = f.read()

        server_thread = threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.1), daemon=True)
        server_thread.start()

        base_url = f"http://127.0.0.1:{port}"

        try:
            # 1. Test GET /data_shape_config.html
            with urllib.request.urlopen(f"{base_url}/data_shape_config.html") as resp:
                self.assertEqual(resp.status, 200)
                html = resp.read().decode("utf-8")
                self.assertIn("cernodata Data Shape & Preset Planner", html)

            # 2. Test GET /api/config
            with urllib.request.urlopen(f"{base_url}/api/config") as resp:
                self.assertEqual(resp.status, 200)
                cfg = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(cfg["default_doc"], "sample_test.pdf")
                self.assertEqual(cfg["default_lang"], "pl")
                self.assertEqual(cfg["default_threshold"], 0.85)
                self.assertIn("preset_weights", cfg)
                self.assertIn("taxonomy_options", cfg)

            # 3. Test POST /api/calculate_scores
            score_req_data = json.dumps({
                "taxonomy": "financial_report",
                "hardware": "workstation_cuda",
                "target": "high_precision_structure",
                "security": "air_gapped_local",
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{base_url}/api/calculate_scores",
                data=score_req_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200)
                calc_resp = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(calc_resp["success"])
                self.assertIn("docling_deep", calc_resp["scores"])
                self.assertEqual(calc_resp["suggested_order"][0], "docling_deep")

            # 4. Test POST /api/submit_plan
            plan_submit_data = json.dumps({
                "document_path": "sample_test.pdf",
                "taxonomy": "scanned_form",
                "hardware": "cloud_cluster",
                "target": "high_precision_structure",
                "security": "hosted_vision_api",
                "language": "en",
                "target_threshold": 0.88,
                "override_primary": "vision_llm_direct",
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{base_url}/api/submit_plan",
                data=plan_submit_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200)
                submit_resp = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(submit_resp["success"])
                self.assertIn("plan", submit_resp)
                self.assertEqual(submit_resp["plan"]["primary_preset"], "vision_llm_direct")

            # Verify saved plan file
            saved_plan_file = os.path.join(self.test_output, "plan.json")
            self.assertTrue(os.path.exists(saved_plan_file))
            loaded = DocumentPlan.load(saved_plan_file)
            self.assertEqual(loaded.primary_preset, "vision_llm_direct")
            self.assertEqual(loaded.taxonomy, "scanned_form")

        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_browser_session_flow(self):
        port = find_available_port(start_port=9300, max_attempts=20)

        # Thread simulating browser client submitting form after server starts
        def simulate_browser_client():
            import time
            base_url = f"http://127.0.0.1:{port}"
            submit_data = json.dumps({
                "document_path": "simulated_doc.pdf",
                "taxonomy": "general_text",
                "hardware": "low_spec_cpu",
                "target": "rapid_approximate",
                "security": "air_gapped_local",
                "language": "en",
                "target_threshold": 0.80,
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{base_url}/api/submit_plan",
                data=submit_data,
                headers={"Content-Type": "application/json"}
            )
            for _ in range(50):
                time.sleep(0.1)
                try:
                    with urllib.request.urlopen(req) as resp:
                        if resp.status == 200:
                            break
                except Exception:
                    pass

        client_thread = threading.Thread(target=simulate_browser_client, daemon=True)
        client_thread.start()

        plan = self.planner.browser_session(
            default_doc="simulated_doc.pdf",
            output_dir=self.test_output,
            port=port,
            open_browser=False
        )

        self.assertIsNotNone(plan)
        self.assertEqual(plan.document_path, "simulated_doc.pdf")
        self.assertEqual(plan.taxonomy, "general_text")
        self.assertEqual(plan.hardware, "low_spec_cpu")
        self.assertEqual(plan.target, "rapid_approximate")
        self.assertEqual(plan.primary_preset, "docling_fast")


if __name__ == "__main__":
    unittest.main()
