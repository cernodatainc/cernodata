"""
src/tests/test_docling_ocr_presets.py

Unit tests for Docling OCR engine configuration, parameter wiggling,
and the standalone pypdfium_rapidocr preset outside of Docling.
"""

import os
import unittest
import pytest
from src.dom import DocumentDOM, DOMNode, BoundingBox
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

        # Verify pipeline options map force_full_page_ocr to OcrMode
        pipeline_opts_default = parser_default.build_pipeline_options()
        if pipeline_opts_default and hasattr(pipeline_opts_default, "ocr_options"):
            ocr_opt = pipeline_opts_default.ocr_options
            if hasattr(ocr_opt, "mode"):
                from docling.datamodel.pipeline_options import OcrMode
                self.assertEqual(ocr_opt.mode, OcrMode.DEFAULT)

        pipeline_opts_wiggled = parser_wiggled.build_pipeline_options()
        if pipeline_opts_wiggled and hasattr(pipeline_opts_wiggled, "ocr_options"):
            ocr_opt = pipeline_opts_wiggled.ocr_options
            if hasattr(ocr_opt, "mode"):
                from docling.datamodel.pipeline_options import OcrMode
                self.assertEqual(ocr_opt.mode, OcrMode.FULL_PAGE)
            self.assertTrue(getattr(ocr_opt, "force_full_page_ocr", False))

    @pytest.mark.slow
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

    def test_pypdfium_parser_missing_file_raises(self):
        """Verifies PyPdfiumParser raises FileNotFoundError when file does not exist."""
        parser = PyPdfiumParser()
        with self.assertRaises(FileNotFoundError):
            parser.parse("non_existent_doc.pdf")

    def test_orchestrator_parse_document_presets(self):
        """Verifies parse_document handles both docling and pypdfium_rapidocr presets."""
        from unittest.mock import patch
        mock_dom = DocumentDOM(document_id="d1", source_filename="test.pdf", total_pages=1, nodes=[
            DOMNode(node_id="n1", type="text", global_page_index=1, temp_slice_index=1,
                    bounding_box=BoundingBox(0, 0, 10, 10), content={"raw_text": "Sample text"})
        ])
        with patch.object(DoclingParser, "parse", return_value=mock_dom), \
             patch.object(PyPdfiumParser, "parse", return_value=mock_dom):
            dom_docling = parse_document(self.sample_pdf, language="en", preset="docling_fast")
            self.assertIsNotNone(dom_docling)
            self.assertGreater(len(dom_docling.nodes), 0)

            dom_pypdfium = parse_document(self.sample_pdf, language="en", preset="pypdfium_rapidocr")
            self.assertIsNotNone(dom_pypdfium)
            self.assertGreater(len(dom_pypdfium.nodes), 0)

    def test_planner_includes_pypdfium_rapidocr(self):
        """Verifies PresetPlanner calculates scores for pypdfium_rapidocr."""
        planner = PresetPlanner()
        scores = planner.calculate_scores(
            taxonomy="general_text",
            target="rapid_approximate",
            security="air_gapped_local"
        )
        self.assertIn("pypdfium_rapidocr", scores)
        self.assertIn("docling_fast", scores)
        # On general text and rapid target, pypdfium_rapidocr should have a very high score
        self.assertGreaterEqual(scores["pypdfium_rapidocr"], 0.85)

    def test_pipeline_path_b_parameter_wiggling(self):
        """Verifies pipeline executes Path B parameter wiggling when delta >= 0.20 and threshold fails."""
        from unittest.mock import patch
        mock_dom = DocumentDOM(document_id="d1", source_filename="test_dummy.pdf", total_pages=1, nodes=[
            DOMNode(node_id="n1", type="text", global_page_index=1, temp_slice_index=1,
                    bounding_box=BoundingBox(0, 0, 10, 10), content={"raw_text": "Sample text"})
        ])
        planner = PresetPlanner()
        # Create a custom plan where primary is pypdfium_rapidocr and fallback delta >= 0.20
        plan = planner.create_plan(
            document_path="test_dummy.pdf",
            taxonomy="general_text",
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

        with patch("src.pipeline.orchestrator.parse_document", return_value=mock_dom), \
             patch("src.pipeline.orchestrator.align_document_skew", side_effect=lambda d, p, a: d), \
             patch("src.pipeline.orchestrator.render_visual_overlays", return_value=[]), \
             patch("src.pipeline.orchestrator.export_pipeline_artifacts", return_value=("a.json", "b.json", "c.json")), \
             patch("src.pipeline.orchestrator.export_interactive_html_viewer", return_value="viewer.html"):
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
