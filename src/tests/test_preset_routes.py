"""
src/tests/test_preset_routes.py

Integration tests for TASK-207: /api/presets, /api/presets/test, /api/config
custom preset hydration, /api/calculate_scores weight merging, and Web UI assets.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from src.parsers.section_ocr import (
    SectionOCRParser,
    get_default_section_parser,
    set_default_section_parser,
)
from src.pipeline.parsers.registry import get_default_parser_registry
from src.pipeline.planner import PresetPlanner
from src.tests.conftest import http_get, http_post_json, running_test_server


class _ProbeHttpHandler(BaseHTTPRequestHandler):
    """Minimal HTTP endpoint responding 200 OK for /api/presets/test reachability probes."""

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        body = json.dumps({"status": "ok"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class TestPresetRoutesAndWebUi(unittest.TestCase):
    """Tests custom preset HTTP routes, registry/planner synchronization, and Web UI assets."""

    probe_server: HTTPServer
    probe_thread: threading.Thread
    probe_url: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.probe_server = HTTPServer(("127.0.0.1", 0), _ProbeHttpHandler)
        cls.probe_url = f"http://127.0.0.1:{cls.probe_server.server_port}/health"
        cls.probe_thread = threading.Thread(
            target=lambda: cls.probe_server.serve_forever(poll_interval=0.05),
            daemon=True,
        )
        cls.probe_thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.probe_server.shutdown()
        cls.probe_server.server_close()

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_preset_routes_")
        self.presets_path = os.path.join(self.test_dir, "custom_presets.json")
        self._prev_parser = get_default_section_parser()
        set_default_section_parser(SectionOCRParser(language="en"))
        reg = get_default_parser_registry()
        self._prev_adapters = list(reg._adapters)
        self._prev_custom_presets = dict(reg._custom_presets)

    def tearDown(self) -> None:
        reg = get_default_parser_registry()
        reg._adapters = self._prev_adapters
        reg._custom_presets = self._prev_custom_presets
        set_default_section_parser(self._prev_parser)
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_get_and_post_presets_syncs_config_registry_and_planner(self) -> None:
        planner = PresetPlanner()
        with running_test_server(
            planner=planner,
            output_dir=self.test_dir,
            custom_presets_path=self.presets_path,
        ) as (_, base_url):
            status, body, _ = http_get(f"{base_url}/api/presets")
            self.assertEqual(status, 200)
            initial = json.loads(body)
            self.assertTrue(initial["success"])
            self.assertEqual(initial["presets"], [])
            recipe_ids = {r["preset_id"] for r in initial["community_recipes"]}
            self.assertIn("tesseract_multilang", recipe_ids)
            self.assertIn("paddleocr_cjk_http", recipe_ids)

            bad_status, bad_data = http_post_json(
                f"{base_url}/api/presets",
                {"preset_id": "invalid_cli", "backend_type": "cli_subprocess"},
            )
            self.assertEqual(bad_status, 400)
            self.assertFalse(bad_data["success"])

            save_status, save_data = http_post_json(
                f"{base_url}/api/presets",
                {
                    "preset_id": "route_custom_cli",
                    "display_name": "Route Custom CLI",
                    "backend_type": "cli_subprocess",
                    "command_template": [sys.executable, "-c", "print('ok')", "{input_path}", "{output_path}"],
                    "output_format": "text",
                    "hardware_weight": "heavy_cpu",
                    "taxonomy_hints": ["scanned_form"],
                    "suitability_weights": {
                        "scanned_form": 0.99,
                        "high_precision_structure": 0.99,
                        "air_gapped_local": 0.99,
                    },
                },
            )
            self.assertEqual(save_status, 200)
            self.assertTrue(save_data["success"])
            self.assertEqual(save_data["preset"]["preset_id"], "route_custom_cli")
            self.assertTrue(os.path.isfile(self.presets_path))
            self.assertIsNotNone(get_default_parser_registry().resolve("route_custom_cli"))

            cfg_status, cfg_body, _ = http_get(f"{base_url}/api/config")
            self.assertEqual(cfg_status, 200)
            cfg = json.loads(cfg_body)
            self.assertIn("route_custom_cli", cfg["preset_weights"])
            user_entries = [item for item in cfg["custom_presets"] if item.get("source") == "user"]
            self.assertEqual([e["preset_id"] for e in user_entries], ["route_custom_cli"])

            score_status, score_data = http_post_json(
                f"{base_url}/api/calculate_scores",
                {
                    "taxonomy": "scanned_form",
                    "target": "high_precision_structure",
                    "security": "air_gapped_local",
                },
            )
            self.assertEqual(score_status, 200)
            self.assertIn("route_custom_cli", score_data["scores"])
            self.assertAlmostEqual(score_data["scores"]["route_custom_cli"], 0.99, places=3)
            self.assertEqual(score_data["suggested_order"][0], "route_custom_cli")

    def test_post_test_preset_cli_and_http_connectivity(self) -> None:
        with running_test_server(
            output_dir=self.test_dir,
            custom_presets_path=self.presets_path,
        ) as (_, base_url):
            ok_status, ok_data = http_post_json(
                f"{base_url}/api/presets/test",
                {
                    "backend_type": "cli_subprocess",
                    "command_template": [sys.executable, "{input_path}", "{output_path}"],
                },
            )
            self.assertEqual(ok_status, 200)
            self.assertTrue(ok_data["reachable"])

            miss_status, miss_data = http_post_json(
                f"{base_url}/api/presets/test",
                {
                    "backend_type": "cli_subprocess",
                    "command_template": ["definitely_nonexistent_ocr_binary_xyz_987", "{input_path}"],
                },
            )
            self.assertEqual(miss_status, 200)
            self.assertFalse(miss_data["reachable"])

            http_ok_status, http_ok_data = http_post_json(
                f"{base_url}/api/presets/test",
                {
                    "backend_type": "http_endpoint",
                    "endpoint_url": self.probe_url,
                },
            )
            self.assertEqual(http_ok_status, 200)
            self.assertTrue(http_ok_data["reachable"])

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                closed_port = sock.getsockname()[1]
            dead_url = f"http://127.0.0.1:{closed_port}/unreachable"
            http_fail_status, http_fail_data = http_post_json(
                f"{base_url}/api/presets/test",
                {
                    "backend_type": "http_endpoint",
                    "endpoint_url": dead_url,
                    "timeout_sec": 1,
                },
            )
            self.assertEqual(http_fail_status, 200)
            self.assertFalse(http_fail_data["reachable"])

    def test_web_ui_html_js_and_css_include_custom_preset_builder(self) -> None:
        with running_test_server(
            output_dir=self.test_dir,
            custom_presets_path=self.presets_path,
        ) as (_, base_url):
            for route in ("/", "/landing", "/data_shape_config.html"):
                st, html_text, _ = http_get(f"{base_url}{route}")
                self.assertEqual(st, 200)
                self.assertIn("customPresetBuilderModal", html_text)
                self.assertIn("openCustomPresetBuilderModal()", html_text)
                self.assertIn("cpRecipeSelect", html_text)
                self.assertIn("cpTestBtn", html_text)

            st_ljs, ljs_text, _ = http_get(f"{base_url}/landing.js")
            self.assertEqual(st_ljs, 200)
            self.assertIn("initCustomPresetBuilderModal", ljs_text)

            st_djs, djs_text, _ = http_get(f"{base_url}/data_shape_config.js")
            self.assertEqual(st_djs, 200)
            self.assertIn("initCustomPresetBuilderModal", djs_text)
            self.assertIn("appendCustomPresetOption", djs_text)
            self.assertIn("testCustomPresetConnection", djs_text)
            self.assertIn("saveCustomPresetFromModal", djs_text)

            for css_route in ("/landing.css", "/data_shape_config.css"):
                st_css, css_text, _ = http_get(f"{base_url}{css_route}")
                self.assertEqual(st_css, 200)
                self.assertIn(".custom-preset-modal-backdrop", css_text)

    def test_api_run_and_rerun_require_preset_without_plan(self) -> None:
        with running_test_server(
            output_dir=self.test_dir,
            custom_presets_path=self.presets_path,
        ) as (server, base_url):
            server.session_context.submitted_plan = None
            run_status, run_data = http_post_json(f"{base_url}/api/run", {"pdf_path": "src/e2e/Document 8.pdf"})
            self.assertEqual(run_status, 400)
            self.assertFalse(run_data.get("success", True))

            rerun_status, rerun_data = http_post_json(f"{base_url}/api/rerun", {"pdf_path": "src/e2e/Document 8.pdf"})
            self.assertEqual(rerun_status, 400)
            self.assertFalse(rerun_data.get("success", True))


if __name__ == "__main__":
    unittest.main()
