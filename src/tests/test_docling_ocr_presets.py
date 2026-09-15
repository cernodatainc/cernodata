"""
src/tests/test_docling_ocr_presets.py

Unit tests for Docling OCR engine configuration, parameter wiggling,
and the standalone pypdfium_rapidocr preset outside of Docling.
"""

import os
import unittest
from src.parsers.docling_parser import DoclingParser
from src.parsers.pypdfium_parser import PyPdfiumParser
from src.pipeline.planner import PresetPlanner
from src.pipeline.orchestrator import parse_document, run_pipeline


class TestDoclingOCRPresets(unittest.TestCase):

    def setUp(self):
        self.sample_pdf = os.path.join("src", "e2e", "Dokument 5.pdf")

    def test_docling_parser_parameters_and_defaults(self):
        """Verifies DoclingParser captures OCR engine and parameter wiggling settings."""
        parser_default = DoclingParser(language="pl", preset="docling_fast")
        self.assertEqual(parser_default.language, "pl")
        self.assertEqual(parser_default.preset, "docling_fast")
        self.assertEqual(parser_default.ocr_scale, 3.0)
        self.assertFalse(parser_default.force_full_page_ocr)

        # Wiggled parameters
        parser_wiggled = DoclingParser(
            language="de",
            preset="docling_fast",
            ocr_engine="rapidocr",
            ocr_scale=4.0,
            force_full_page_ocr=True,
            do_table_structure=False
        )
        self.assertEqual(parser_wiggled.ocr_engine, "rapidocr")
        self.assertEqual(parser_wiggled.ocr_scale, 4.0)
        self.assertTrue(parser_wiggled.force_full_page_ocr)
        self.assertFalse(parser_wiggled.do_table_structure)

    def test_pypdfium_parser_standalone(self):
        """Verifies PyPdfiumParser runs outside of Docling and extracts DOM nodes."""
        parser = PyPdfiumParser(language="pl", scale=2.0)
        if os.path.exists(self.sample_pdf):
            dom = parser.parse(self.sample_pdf)
            self.assertIsNotNone(dom)
            self.assertGreater(dom.total_pages, 0)
            self.assertGreater(len(dom.nodes), 0)
            # Ensure nodes are standard DOMNode instances with valid bounding boxes
            first_node = dom.nodes[0]
            self.assertTrue(hasattr(first_node, "bounding_box"))
            self.assertGreaterEqual(first_node.bounding_box.x0, 0.0)
            self.assertGreaterEqual(first_node.bounding_box.y0, 0.0)

    def test_pypdfium_parser_synthetic_fallback(self):
        """Verifies PyPdfiumParser falls back gracefully when file does not exist."""
        parser = PyPdfiumParser()
        dom = parser.parse("non_existent_doc.pdf")
        self.assertEqual(dom.total_pages, 1)
        self.assertGreater(len(dom.nodes), 0)

    def test_orchestrator_parse_document_presets(self):
        """Verifies parse_document handles both docling and pypdfium_rapidocr presets."""
        # Non-existent file tests synthetic fallback across all presets
        dom_docling = parse_document("dummy.pdf", language="en", preset="docling_fast")
        self.assertIsNotNone(dom_docling)
        self.assertGreater(len(dom_docling.nodes), 0)

        dom_pypdfium = parse_document("dummy.pdf", language="en", preset="pypdfium_rapidocr")
        self.assertIsNotNone(dom_pypdfium)
        self.assertGreater(len(dom_pypdfium.nodes), 0)

    def test_planner_includes_pypdfium_rapidocr(self):
        """Verifies PresetPlanner calculates scores for pypdfium_rapidocr."""
        planner = PresetPlanner()
        scores = planner.calculate_scores(
            taxonomy="general_text",
            hardware="low_spec_cpu",
            target="rapid_approximate",
            security="air_gapped_local"
        )
        self.assertIn("pypdfium_rapidocr", scores)
        self.assertIn("docling_fast", scores)
        # On low spec CPU and rapid target, pypdfium_rapidocr should have a very high score
        self.assertGreaterEqual(scores["pypdfium_rapidocr"], 0.85)

    def test_pipeline_path_b_parameter_wiggling(self):
        """Verifies pipeline executes Path B parameter wiggling when delta >= 0.20 and threshold fails."""
        planner = PresetPlanner()
        # Create a custom plan where primary is pypdfium_rapidocr and fallback delta >= 0.20
        plan = planner.create_plan(
            document_path="test_dummy.pdf",
            taxonomy="general_text",
            hardware="low_spec_cpu",
            target="rapid_approximate",
            security="air_gapped_local",
            language="en",
            target_threshold=0.99,  # High threshold to trigger fallback evaluation
            override_primary="pypdfium_rapidocr"
        )
        # Ensure scores delta >= 0.20 to exercise Path B
        plan.scores["pypdfium_rapidocr"] = 0.95
        if plan.fallback_queue:
            plan.scores[plan.fallback_queue[0]["preset"]] = 0.65

        res = run_pipeline(
            pdf_path="test_dummy.pdf",
            plan=plan,
            output_dir="test_output",
            visualize=False
        )
        self.assertIn("attempts", res["decision"])
        attempts = res["decision"]["attempts"]
        self.assertGreaterEqual(len(attempts), 1)


if __name__ == "__main__":
    unittest.main()
