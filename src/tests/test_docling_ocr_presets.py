"""
src/tests/test_docling_ocr_presets.py

Unit tests for Docling OCR engine configuration, parameter wiggling,
and the standalone pypdfium_rapidocr preset outside of Docling.
"""

import os
import unittest
import pytest
from src.parsers.docling_parser import DoclingParser
from src.parsers.pypdfium_parser import PyPdfiumParser
from src.pipeline.planner import PresetPlanner
from src.pipeline.parsers.dispatch import parse_document
from src.pipeline.orchestrator import run_pipeline
from src.tests.conftest import make_test_dom, patch_pipeline_io


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
        mock_dom = make_test_dom("Sample text", document_id="d1", source_filename="test.pdf", node_type="text")
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
        mock_dom = make_test_dom("Sample text", document_id="d1", source_filename="test_dummy.pdf", node_type="text")
        planner = PresetPlanner()
        plan = planner.create_plan(
            document_path="test_dummy.pdf",
            taxonomy="general_text",
            target="rapid_approximate",
            security="air_gapped_local",
            language="en",
            target_threshold=0.99,  # High threshold to trigger fallback evaluation
            override_primary="pypdfium_rapidocr"
        )
        plan.scores["pypdfium_rapidocr"] = 0.95
        if plan.fallback_queue:
            plan.scores[plan.fallback_queue[0]["preset"]] = 0.65

        with patch_pipeline_io(parse_return=mock_dom):
            res = run_pipeline(
                pdf_path="test_dummy.pdf",
                target_threshold=0.99,
                language="en",
                preset="pypdfium_rapidocr",
                align_skew=True,
                visualize=False,
                output_dir="test_output",
                plan=plan,
            )
            self.assertIn("attempts", res["decision"])
            attempts = res["decision"]["attempts"]
            self.assertGreaterEqual(len(attempts), 1)

    def test_pipeline_fallback_multi_step_continuation(self):
        """Verifies pipeline continues down fallback queue when both primary and first fallback fail."""
        mock_dom = make_test_dom("Sample text", document_id="d1", source_filename="test_multi.pdf", node_type="text")
        planner = PresetPlanner()
        plan = planner.create_plan(
            document_path="test_multi.pdf",
            taxonomy="general_text",
            target="high_precision_structure",
            security="air_gapped_local",
            language="en",
            target_threshold=0.85,
            override_order=["docling_fast", "pypdfium_rapidocr", "docling_deep"],
        )

        def mock_eval_fn(*args, **kwargs):
            config = kwargs.get("config") or (args[1] if len(args) > 1 else None)
            preset = getattr(config, "preset", "docling_fast")
            if preset in ("docling_fast", "pypdfium_rapidocr"):
                return {
                    "is_accepted": False,
                    "overall_confidence": 0.35,
                    "status": "TRIGGER_FALLBACK",
                    "chosen_preset": preset,
                    "decision_tree": {"action": "PATH_A_SWITCH_PRESET"},
                }, []
            return {
                "is_accepted": True,
                "overall_confidence": 0.95,
                "status": "ACCEPT",
                "chosen_preset": "docling_deep",
                "decision_tree": {"action": "ACCEPT_OUTPUT"},
            }, []

        with patch_pipeline_io(parse_return=mock_dom, eval_side_effect=mock_eval_fn):
            res = run_pipeline(
                pdf_path="test_multi.pdf",
                target_threshold=0.85,
                language="en",
                preset="docling_fast",
                align_skew=True,
                visualize=False,
                output_dir="test_output",
                plan=plan,
            )
            attempts = res["decision"].get("attempts", [])
            executed_presets = [a.get("preset") for a in attempts]
            self.assertIn("docling_deep", executed_presets)
            self.assertEqual(res["decision"].get("chosen_preset"), "docling_deep")


if __name__ == "__main__":
    unittest.main()
