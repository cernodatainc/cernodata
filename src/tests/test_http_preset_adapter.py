"""
src/tests/test_http_preset_adapter.py

Unit tests for HttpPresetAdapter and SectionOCRParser HTTP endpoint engine.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List
from PIL import Image

from src.parsers.section_ocr import SectionOCRParser
from src.pipeline.parsers.adapters import ParserExecutionOptions
from src.pipeline.parsers.http_adapter import HttpPresetAdapter
from src.schemas.custom_preset import CustomPresetConfig, PresetBackendType


class _MockOcrHttpHandler(BaseHTTPRequestHandler):
    """Minimal local HTTP server handler simulating an external OCR microservice."""

    received_requests: List[Dict[str, Any]] = []
    response_mode: str = "pages"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        payload = json.loads(raw) if raw else {}
        self.__class__.received_requests.append(payload)

        mode = self.__class__.response_mode
        if mode == "dom":
            reply: Dict[str, Any] = {
                "document_id": "http_dom_1",
                "source_filename": payload.get("filename", "sample.pdf"),
                "total_pages": 1,
                "nodes": [
                    {
                        "node_id": "http_n1",
                        "type": "heading",
                        "global_page_index": 1,
                        "temp_slice_index": 1,
                        "bounding_box": {"x0": 20.0, "y0": 20.0, "x1": 300.0, "y1": 60.0},
                        "content": {"raw_text": "Remote DOM Heading"},
                    }
                ],
            }
        elif mode == "pages":
            reply = {
                "pages": [
                    {"page_index": 1, "text": "Page one paragraph.\n\nSecond block."},
                    {"page_index": 2, "text": "Page two text."},
                ]
            }
        else:
            reply = {"text": "Plain remote OCR output", "confidence": 0.94}

        body = json.dumps(reply).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class TestHttpPresetAdapter(unittest.TestCase):
    """Verifies HttpPresetAdapter POST contract, DOM reconstruction, and SectionOCRParser integration."""

    server: HTTPServer
    thread: threading.Thread
    base_url: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = HTTPServer(("127.0.0.1", 0), _MockOcrHttpHandler)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}/ocr"
        cls.thread = threading.Thread(target=lambda: cls.server.serve_forever(poll_interval=0.05), daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self) -> None:
        _MockOcrHttpHandler.received_requests.clear()
        _MockOcrHttpHandler.response_mode = "pages"
        self.test_dir = tempfile.mkdtemp(prefix="test_http_adapter_")
        self.dummy_pdf = os.path.join(self.test_dir, "invoice.pdf")
        with open(self.dummy_pdf, "wb") as fp:
            fp.write(b"%PDF-1.4\n%http-test\n")

    def tearDown(self) -> None:
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_can_handle_exact_preset_only(self) -> None:
        cfg = CustomPresetConfig(
            preset_id="paddle_http",
            display_name="Paddle HTTP",
            backend_type=PresetBackendType.HTTP_ENDPOINT,
            endpoint_url=self.base_url,
        )
        adapter = HttpPresetAdapter(cfg)
        self.assertTrue(adapter.can_handle("paddle_http"))
        self.assertFalse(adapter.can_handle("docling_fast"))

    def test_parse_pages_response_and_request_payload(self) -> None:
        _MockOcrHttpHandler.response_mode = "pages"
        adapter = HttpPresetAdapter("paddle_http", endpoint_url=self.base_url)
        dom = adapter.parse(
            self.dummy_pdf,
            ParserExecutionOptions(preset="paddle_http", language="ja", extra_parameters={"dpi": 300}),
        )

        self.assertEqual(len(_MockOcrHttpHandler.received_requests), 1)
        sent = _MockOcrHttpHandler.received_requests[0]
        self.assertEqual(sent["filename"], "invoice.pdf")
        self.assertEqual(sent["preset"], "paddle_http")
        self.assertEqual(sent["language"], "ja")
        self.assertEqual(sent["parameters"]["dpi"], 300)
        self.assertEqual(base64.b64decode(sent["pdf_base64"]), b"%PDF-1.4\n%http-test\n")

        self.assertEqual(dom.total_pages, 2)
        self.assertEqual(len(dom.nodes), 3)
        self.assertEqual(dom.nodes[0].global_page_index, 1)
        self.assertEqual(dom.nodes[2].global_page_index, 2)
        self.assertEqual(dom.nodes[2].content["raw_text"], "Page two text.")

    def test_parse_full_dom_response(self) -> None:
        _MockOcrHttpHandler.response_mode = "dom"
        adapter = HttpPresetAdapter("remote_dom", endpoint_url=self.base_url, output_format="cernodata_dom_json")
        dom = adapter.parse(self.dummy_pdf, ParserExecutionOptions(preset="remote_dom"))
        self.assertEqual(dom.document_id, "http_dom_1")
        self.assertEqual(len(dom.nodes), 1)
        self.assertEqual(dom.nodes[0].type, "heading")
        self.assertEqual(dom.nodes[0].content["raw_text"], "Remote DOM Heading")

    def test_parse_plain_text_response(self) -> None:
        _MockOcrHttpHandler.response_mode = "text"
        adapter = HttpPresetAdapter("remote_text", endpoint_url=self.base_url)
        dom = adapter.parse(self.dummy_pdf, ParserExecutionOptions(preset="remote_text"))
        self.assertEqual(len(dom.nodes), 1)
        self.assertEqual(dom.nodes[0].content["raw_text"], "Plain remote OCR output")

    def test_section_ocr_http_endpoint_engine(self) -> None:
        _MockOcrHttpHandler.response_mode = "text"
        parser = SectionOCRParser(language="en")
        engine = parser._create_http_endpoint_engine(self.base_url, preset_id="remote_cutout")
        parser.register_engine("remote_cutout", engine)

        img = Image.new("RGB", (60, 24), color="white")
        res = parser.parse_image(img, engine_name="remote_cutout")
        self.assertTrue(res["success"])
        self.assertEqual(res["text"], "Plain remote OCR output")
        self.assertAlmostEqual(res["confidence"], 0.94, places=2)
        self.assertIn("image_base64", _MockOcrHttpHandler.received_requests[-1])


if __name__ == "__main__":
    unittest.main()
