"""
src/tests/test_section_ocr.py

Unit tests for SectionOCRParser, targeted section parsing,
and the /api/parse_section_ocr live server endpoint.
"""

import os
import io
import re
import json
import base64
import unittest
import threading
import urllib.request
from http.server import HTTPServer
from PIL import Image, ImageDraw

from src.dom.bounding_box import BoundingBox
from src.parsers.section_ocr import (
    SectionOCRParser,
    get_default_section_parser,
    normalize_bbox_coords,
    normalize_to_pil,
    parse_image_ocr,
    parse_section_from_pdf,
    set_default_section_parser,
)
from src.pipeline.server import PipelineViewerHandler


def _create_test_image_with_text(text: str = "Total Due: $1,250.00") -> Image.Image:
    """Creates a synthetic RGB image containing readable printed text."""
    img = Image.new("RGB", (320, 80), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((15, 25), text, fill="black")
    return img


def _image_to_base64_data_uri(img: Image.Image) -> str:
    """Encodes a PIL image into a base64 data URI."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


class TestSectionOCRParser(unittest.TestCase):

    def test_strict_emoji_ban(self):
        """Verifies no emojis exist in parser or test source files."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        parser_path = os.path.join(base_dir, "parsers", "section_ocr.py")
        test_path = os.path.abspath(__file__)

        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)

        for filepath in (parser_path, test_path):
            self.assertTrue(os.path.exists(filepath), f"File {filepath} not found.")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertFalse(
                bool(emoji_pattern.search(content)),
                f"Emoji detected in {filepath}!"
            )

    def test_parse_pil_image_with_text(self):
        """Verifies OCR parsing on a PIL Image containing text."""
        test_text = "Account ID: ACC-8842"
        img = _create_test_image_with_text(test_text)

        parser = SectionOCRParser()
        result = parser.parse_image(img)

        self.assertTrue(result["success"])
        self.assertIsNone(result["error"])
        self.assertGreater(result["confidence"], 0.5)
        self.assertIn("Account", result["text"])
        self.assertIn("ACC-8842", result["text"])
        self.assertGreaterEqual(len(result["lines"]), 1)

    def test_parse_base64_data_uri(self):
        """Verifies OCR parsing when image is supplied as base64 data URI string."""
        test_text = "Invoice Number: INV-2026"
        img = _create_test_image_with_text(test_text)
        data_uri = _image_to_base64_data_uri(img)

        result = parse_image_ocr(data_uri)

        self.assertTrue(result["success"])
        self.assertIn("Invoice", result["text"])
        self.assertIn("INV-2026", result["text"])
        self.assertGreater(result["confidence"], 0.7)

    def test_parse_image_bytes(self):
        """Verifies OCR parsing when image is supplied as raw PNG bytes."""
        img = _create_test_image_with_text("Subtotal: $450.00")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        raw_bytes = buf.getvalue()

        result = parse_image_ocr(raw_bytes)
        self.assertTrue(result["success"])
        self.assertIn("Subtotal", result["text"])

    def test_parse_blank_image(self):
        """Verifies OCR handles blank white image gracefully without errors."""
        blank_img = Image.new("RGB", (200, 100), color="white")
        result = parse_image_ocr(blank_img)

        self.assertTrue(result["success"])
        self.assertEqual(result["text"], "")
        self.assertEqual(result["lines"], [])

    def test_parse_invalid_input(self):
        """Verifies unsupported input types return a structured failure dictionary."""
        parser = SectionOCRParser()
        result = parser.parse_image(12345)  # type: ignore

        self.assertFalse(result["success"])
        self.assertIn("Unsupported image input type", result["error"])

    def test_parse_section_from_pdf(self):
        """Verifies cropping and parsing a section from an existing PDF document."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pdf_candidates = [
            os.path.join(base_dir, "e2e", "Dokument 5.pdf"),
            os.path.join(base_dir, "e2e", "sample.pdf")
        ]
        pdf_path = next((p for p in pdf_candidates if os.path.exists(p)), None)
        if not pdf_path:
            self.skipTest("No test PDF found for PDF crop verification.")

        # Crop a section from page 1
        bbox = {"x0": 40.0, "y0": 30.0, "x1": 550.0, "y1": 120.0}
        result = parse_section_from_pdf(pdf_path, page_number=1, bbox=bbox)

        self.assertTrue(result["success"])
        self.assertIsInstance(result["text"], str)

    def test_server_ocr_endpoint(self):
        """Verifies POST /api/parse_section_ocr HTTP server endpoint."""
        server_address = ("127.0.0.1", 0)  # OS allocates free port
        httpd = HTTPServer(server_address, PipelineViewerHandler)
        assigned_port = httpd.server_port

        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()

        base_url = f"http://127.0.0.1:{assigned_port}"

        try:
            # 1. Test POST /api/parse_section_ocr with base64 image
            test_img = _create_test_image_with_text("Order Code: ORD-7719")
            data_uri = _image_to_base64_data_uri(test_img)

            payload = json.dumps({
                "node_id": "node_p1_n3",
                "image_base64": data_uri,
                "language": "en"
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{base_url}/api/parse_section_ocr",
                data=payload,
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200)
                body = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(body["success"])
                self.assertEqual(body["node_id"], "node_p1_n3")
                self.assertIn("ORD-7719", body["text"])
                self.assertGreater(body["confidence"], 0.5)

            # 2. Test missing payload returns 400
            empty_req = urllib.request.Request(
                f"{base_url}/api/parse_section_ocr",
                data=json.dumps({"node_id": "missing_data"}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(empty_req)
            self.assertEqual(ctx.exception.code, 400)
            ctx.exception.close()

        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_custom_engine_dependency_injection(self) -> None:
        """Verifies custom engine dependency injection without loading default models."""
        class MockEngine:
            def __call__(self, img_arr: object) -> object:
                class MockResult:
                    txts = ["Custom Extracted Header", "Custom Value 123"]
                    scores = [0.99, 0.95]
                    boxes = [
                        [[10, 10], [100, 10], [100, 30], [10, 30]],
                        [[10, 40], [100, 40], [100, 60], [10, 60]],
                    ]
                return MockResult()

        mock_engine = MockEngine()
        parser = SectionOCRParser(engine=mock_engine)
        self.assertIs(parser.engine, mock_engine)

        dummy_img = Image.new("RGB", (120, 80), color="white")
        result = parser.parse_image(dummy_img)

        self.assertTrue(result["success"])
        self.assertIn("Custom Extracted Header", result["text"])
        self.assertIn("Custom Value 123", result["text"])
        self.assertEqual(len(result["lines"]), 2)
        self.assertEqual(result["confidence"], 0.97)

    def test_custom_engine_factory(self) -> None:
        """Verifies engine_factory initializes custom engine lazily."""
        calls: list[bool] = []

        def factory() -> object:
            calls.append(True)
            return lambda arr: {"txts": ["Factory Text"], "scores": [0.92], "boxes": [None]}

        parser = SectionOCRParser(engine_factory=factory)
        self.assertEqual(len(calls), 0)

        dummy_img = Image.new("RGB", (50, 50), color="white")
        result = parser.parse_image(dummy_img)
        self.assertEqual(len(calls), 1)
        self.assertTrue(result["success"])
        self.assertEqual(result["text"], "Factory Text")

    def test_normalize_bbox_coords(self) -> None:
        """Verifies coordinate normalization across various bounding box representations."""
        # 1. BoundingBox instance
        bbox_obj = BoundingBox(x0=12.5, y0=24.0, x1=100.0, y1=85.5)
        self.assertEqual(normalize_bbox_coords(bbox_obj), (12.5, 24.0, 100.0, 85.5))

        # 2. Dict with x0/y0/x1/y1
        dict_coords = {"x0": 10.0, "y0": 20.0, "x1": 50.0, "y1": 60.0}
        self.assertEqual(normalize_bbox_coords(dict_coords), (10.0, 20.0, 50.0, 60.0))

        # 3. Dict with left/top/right/bottom
        dict_ltrb = {"left": 5.0, "top": 15.0, "right": 45.0, "bottom": 55.0}
        self.assertEqual(normalize_bbox_coords(dict_ltrb), (5.0, 15.0, 45.0, 55.0))

        # 4. Tuple and list
        self.assertEqual(normalize_bbox_coords((1.0, 2.0, 3.0, 4.0)), (1.0, 2.0, 3.0, 4.0))
        self.assertEqual(normalize_bbox_coords([10, 20, 30, 40]), (10.0, 20.0, 30.0, 40.0))

        # 5. Unsupported type raises TypeError
        with self.assertRaises(TypeError):
            normalize_bbox_coords("invalid")  # type: ignore

    def test_normalize_to_pil_with_file_path(self) -> None:
        """Verifies normalize_to_pil loads an image from an on-disk file path."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            sample_img = Image.new("RGB", (64, 32), color="blue")
            sample_img.save(tmp_path, format="PNG")

            loaded = normalize_to_pil(tmp_path)
            self.assertIsInstance(loaded, Image.Image)
            self.assertEqual(loaded.size, (64, 32))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_default_parser_lifecycle(self) -> None:
        """Verifies getting and setting default SectionOCRParser singleton."""
        orig = get_default_section_parser()
        try:
            custom = SectionOCRParser(language="de")
            set_default_section_parser(custom)
            self.assertIs(get_default_section_parser(), custom)
        finally:
            set_default_section_parser(orig)


if __name__ == "__main__":
    unittest.main()
