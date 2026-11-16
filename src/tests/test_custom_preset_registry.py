"""
src/tests/test_custom_preset_registry.py

Tests for TASK-204: DoclingPresetAdapter scoping, ParserPresetRegistry.load_custom_presets,
IngestionConfig.custom_presets_path, and DocumentParserDispatcher auto-loading.
"""

from __future__ import annotations

import json
import os
import shutil
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
from src.pipeline.parsers.adapters import DoclingPresetAdapter
from src.pipeline.parsers.cli_adapter import SubprocessCliPresetAdapter
from src.pipeline.parsers.dispatch import DocumentParserDispatcher
from src.pipeline.parsers.http_adapter import HttpPresetAdapter
from src.pipeline.parsers.registry import ParserPresetRegistry
from src.pipeline.planner.models import IngestionConfig
from src.schemas.custom_preset import (
    CustomPresetConfig,
    PresetBackendType,
    save_custom_presets_file,
)


class _RegistryMockHttpHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler returning static OCR JSON for registry dispatch tests."""

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        _ = self.rfile.read(length)
        body = json.dumps({"text": "HTTP Registry Result"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class TestCustomPresetRegistry(unittest.TestCase):
    """Verifies custom preset loading, adapter precedence, and dispatcher integration."""

    server: HTTPServer
    thread: threading.Thread
    http_url: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = HTTPServer(("127.0.0.1", 0), _RegistryMockHttpHandler)
        cls.http_url = f"http://127.0.0.1:{cls.server.server_port}/ocr"
        cls.thread = threading.Thread(
            target=lambda: cls.server.serve_forever(poll_interval=0.05),
            daemon=True,
        )
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self) -> None:
        self._prev_section_parser = get_default_section_parser()
        set_default_section_parser(SectionOCRParser(language="en"))
        self.test_dir = tempfile.mkdtemp(prefix="test_custom_registry_")
        self.dummy_pdf = os.path.join(self.test_dir, "doc.pdf")
        with open(self.dummy_pdf, "wb") as fp:
            fp.write(b"%PDF-1.4\n%registry-test\n")

    def tearDown(self) -> None:
        set_default_section_parser(self._prev_section_parser)
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_docling_adapter_does_not_swallow_non_docling_presets(self) -> None:
        docling = DoclingPresetAdapter()
        self.assertTrue(docling.can_handle("docling_fast"))
        self.assertTrue(docling.can_handle("docling_deep"))
        self.assertTrue(docling.can_handle("docling_v2"))
        self.assertFalse(docling.can_handle("vision_llm_direct"))
        self.assertFalse(docling.can_handle("custom_cli_ocr"))

        registry = ParserPresetRegistry.create_default()
        self.assertIsNone(registry.resolve("vision_llm_direct"))
        self.assertIsNone(registry.resolve("unknown_preset_xyz"))

    def test_load_custom_presets_precedence_and_section_parser_registration(self) -> None:
        manifest_path = os.path.join(self.test_dir, "custom_presets.json")
        cli_script = "import sys; open(sys.argv[1], 'w', encoding='utf-8').write('CLI Manifest Output')"
        cli_cfg = CustomPresetConfig(
            preset_id="custom_cli_preset",
            display_name="Custom CLI",
            backend_type=PresetBackendType.CLI_SUBPROCESS,
            command_template=[sys.executable, "-c", cli_script, "{output_path}"],
        )
        http_cfg = CustomPresetConfig(
            preset_id="custom_http_preset",
            display_name="Custom HTTP",
            backend_type=PresetBackendType.HTTP_ENDPOINT,
            endpoint_url=self.http_url,
        )
        save_custom_presets_file(manifest_path, [cli_cfg, http_cfg])

        registry = ParserPresetRegistry.create_default()
        loaded = registry.load_custom_presets(manifest_path, include_community_recipes=False)
        self.assertEqual(len(loaded), 2)

        cli_adapter = registry.resolve("custom_cli_preset")
        http_adapter = registry.resolve("custom_http_preset")
        self.assertIsInstance(cli_adapter, SubprocessCliPresetAdapter)
        self.assertIsInstance(http_adapter, HttpPresetAdapter)

        section_parser = get_default_section_parser()
        self.assertIn("custom_cli_preset", section_parser._engine_registry)
        self.assertIn("custom_http_preset", section_parser._engine_registry)
        self.assertIn("custom_cli_preset", section_parser.get_available_engines())
        self.assertIn("custom_http_preset", section_parser.get_available_engines())

    def test_dispatcher_autoloads_custom_presets_from_ingestion_config(self) -> None:
        manifest_path = os.path.join(self.test_dir, "presets.json")
        cli_script = "import sys; open(sys.argv[1], 'w', encoding='utf-8').write('Dispatched Custom Text')"
        cli_cfg = CustomPresetConfig(
            preset_id="docling_override_test",
            display_name="Override Test",
            backend_type=PresetBackendType.CLI_SUBPROCESS,
            command_template=[sys.executable, "-c", cli_script, "{output_path}"],
        )
        save_custom_presets_file(manifest_path, [cli_cfg])

        cfg = IngestionConfig.from_dict({
            "preset": "docling_override_test",
            "custom_presets_path": manifest_path,
        })
        self.assertEqual(cfg.custom_presets_path, manifest_path)

        registry = ParserPresetRegistry.create_default()
        dispatcher = DocumentParserDispatcher(registry=registry)
        dom = dispatcher.parse(self.dummy_pdf, config=cfg)

        self.assertEqual(len(dom.nodes), 1)
        self.assertEqual(dom.nodes[0].content["raw_text"], "Dispatched Custom Text")

    def test_dispatcher_autoloads_http_preset_from_config(self) -> None:
        manifest_path = os.path.join(self.test_dir, "http_presets.json")
        http_cfg = CustomPresetConfig(
            preset_id="remote_ocr_service",
            display_name="Remote OCR",
            backend_type=PresetBackendType.HTTP_ENDPOINT,
            endpoint_url=self.http_url,
        )
        save_custom_presets_file(manifest_path, [http_cfg])

        cfg = IngestionConfig(preset="remote_ocr_service", custom_presets_path=manifest_path)
        dispatcher = DocumentParserDispatcher(registry=ParserPresetRegistry.create_default())
        dom = dispatcher.parse(self.dummy_pdf, config=cfg)

        self.assertEqual(len(dom.nodes), 1)
        self.assertEqual(dom.nodes[0].content["raw_text"], "HTTP Registry Result")


if __name__ == "__main__":
    unittest.main()
