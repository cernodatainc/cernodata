"""
src/tests/test_bugfixes_regression.py

Regression test suite verifying fixes across schemas, quality layers, parsers,
server caching/session management, and viewer template rendering.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from src.dom import BoundingBox, DOMNode
from src.parsers.docling_helpers import build_node_content, extract_page_no_and_bbox, fallback_top_left_bbox
from src.parsers.ocr_flags import parse_ocr_custom_flags
from src.parsers.ocr_imaging import normalize_to_pil
from src.parsers.ocr_models import normalize_bbox_coords
from src.parsers.pypdfium_parser import _convert_ocr_box_to_bbox
from src.parsers.section_ocr import SectionOCRParser
from src.parsers.table_parser import parse_docling_table, parse_markdown_table, parse_table_content
from src.pipeline.parsers.custom_output import convert_dom_dict_to_dom
from src.pipeline.server.http_utils import parse_run_dir_and_step
from src.pipeline.server.preset_cache import PresetCache
from src.pipeline.server.run_mapping_synthesis import merge_persistent_runs
from src.pipeline.server.run_mappings import load_persistent_mappings, register_document_path
from src.quality.evaluator import evaluate_page_confidence
from src.quality.garbage import compute_garbage_ratio
from src.quality.handlers import DiacriticsLayerHandler, SymbolsLayerHandler, get_suppressed_violation_lookup
from src.quality.handlers_structural import GeometryLayerHandler, TablesLayerHandler
from src.quality.language import compute_language_score
from src.quality.languages.models import LanguageConfig
from src.quality.layers import normalize_layer_name
from src.quality.materialization import MaterializedVerificationResult
from src.quality.table_validator import check_table_assertion, compute_grid_consistency
from src.quality.violations import detect_quality_violations
from src.schemas.custom_preset import ParameterWiggleSpec
from src.schemas.dom import BoundingBoxSchema, DocumentDOMSchema
from src.schemas.test_suite import TableAssertion
from src.schemas.violations import parse_violations_payload
from src.tests.conftest import make_test_dom, make_test_node
from src.visualization.viewer.templates import build_viewer_html


class TestBugfixesRegression(unittest.TestCase):
    """Regression coverage for schema, quality, parser, server, and visualization fixes."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="cernodata_bugfix_reg_")

    def tearDown(self) -> None:
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_document_level_violation_schema_and_dom_extras(self) -> None:
        payload = [
            {
                "violation_id": "v_doc",
                "global_page_index": 1,
                "node_id": None,
                "type": "structure",
                "rule_type": "required_header_missing",
                "severity": "HIGH",
                "suggested_correction": "Overview",
                "description": "Missing overview header",
            }
        ]
        parsed = parse_violations_payload(payload)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].node_id, "")
        self.assertEqual(parsed[0].suggested_correction, "Overview")

        bbox = BoundingBoxSchema.from_raw(
            {"x0": 1.0, "y0": 2.0, "x1": 10.0, "y1": 20.0, "angle": 12.5, "quad": [[1.0, 2.0], [10.0, 2.0]]}
        )
        self.assertEqual(bbox.angle, 12.5)
        self.assertEqual(bbox.quad, [[1.0, 2.0], [10.0, 2.0]])

        dom_schema = DocumentDOMSchema.model_validate({
            "document_id": "d1",
            "source_filename": "s.pdf",
            "total_pages": 1,
            "nodes": [],
            "metadata": {"preset": "custom_x"},
        })
        self.assertEqual(dom_schema.metadata, {"preset": "custom_x"})

    def test_structural_tables_and_geometry_evaluation_and_node_violations(self) -> None:
        md_node = make_test_node("| A | B |\n| --- | --- |\n| 1 | 2 |", node_id="t_md", node_type="table_grid")
        self.assertGreater(TablesLayerHandler().evaluate_node(md_node), 0.9)

        ragged_node = DOMNode(
            node_id="t_ragged",
            type="table_grid",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(0.0, 0.0, 100.0, 50.0),
            content={"raw_text": "ragged", "rows": [["A", "B", "C"], ["1"], ["2"], ["3"]]},
        )
        empty_heading = make_test_node("", node_id="h_empty", node_type="heading")
        neg_node = make_test_node("Neg", node_id="n_neg", bbox=BoundingBox(-5.0, 0.0, 50.0, 20.0))
        self.assertEqual(GeometryLayerHandler().evaluate_node(neg_node), 0.0)

        dom = make_test_dom(nodes=[empty_heading, ragged_node, neg_node], document_id="doc_struct")
        viols = detect_quality_violations(dom, layers=["structure", "tables", "geometry"])
        self.assertGreaterEqual(len(viols), 3)
        self.assertTrue(len(empty_heading.violations) >= 1)
        self.assertTrue(len(ragged_node.violations) >= 1)
        self.assertTrue(len(neg_node.violations) >= 1)

        # Suppress structure violation on empty_heading and verify re-evaluation preserves suppression
        empty_heading.violations[0]["suppressed"] = True
        detect_quality_violations(dom, layers=["structure"])
        self.assertTrue(empty_heading.violations[0]["suppressed"])

    def test_suppression_lookup_and_shifted_ids_and_diacritics_alias(self) -> None:
        node = make_test_node("Infolinia w piqtku.", node_id="n_shift")
        node.violations = [
            {"violation_id": "viol_p1_v1", "rule_type": "garbage_character_ratio", "type": "symbols", "suppressed": False},
            {"violation_id": "viol_p1_v2", "rule_type": "ocr_character_substitution", "type": "diacritic", "suppressed": True},
        ]
        lookup = get_suppressed_violation_lookup(node)
        self.assertTrue(lookup["diacritic"])

        dom = make_test_dom(nodes=[node], document_id="doc_shift")
        viols = detect_quality_violations(dom, language="pl", layers=["diacritics"])
        self.assertEqual(len(viols), 1)
        self.assertTrue(viols[0]["suppressed"])

        self.assertEqual(DiacriticsLayerHandler().evaluate_node(node, language="pl", suppressed_types={"diacritics": True}), 1.0)
        node.violations = [{"type": "diacritics", "suppressed": True}]
        self.assertEqual(DiacriticsLayerHandler().compute_page_penalty([node], language="pl"), 0.0)

    def test_diacritics_word_boundary_auto_lang_and_garbage_false_positives(self) -> None:
        dom = make_test_dom("Zapytanie sql oraz q w faq.", document_id="doc_wb", node_id="n_wb")
        viols = detect_quality_violations(dom, language="pl", layers=["diacritics"])
        self.assertEqual(len(viols), 1)
        self.assertEqual(viols[0]["suggestion"], "Zapytanie sql oraz ą w faq.")

        standalone = DiacriticsLayerHandler().detect_violations(make_test_dom("Spotkanie w piqtku.", node_id="n1"), language="pl")
        self.assertEqual(len(standalone), 1)
        self.assertGreater(DiacriticsLayerHandler().compute_page_penalty([make_test_node("Spotkanie w piqtku.")], language="pl"), 0.0)

        self.assertLess(compute_language_score("Sprawdź termin wykupu swoich obligacji w piqtku.", language="auto"), 1.0)
        self.assertLess(evaluate_page_confidence([make_test_node("Sprawdź termin wykupu swoich obligacji w piqtku.")], language="auto"), 1.0)

        self.assertEqual(compute_garbage_ratio("Il y a un chat et le chien de la dame."), 0.0)
        self.assertEqual(compute_garbage_ratio("1. Introduction"), 0.0)

        tbl_node = make_test_node("| Item | Qty |\n| --- | --- |\n| Pen | 2 |", node_id="t1", node_type="table_grid")
        self.assertEqual(SymbolsLayerHandler().check_node_violations(tbl_node, tbl_node.content["raw_text"], 1), [])

        cfg = LanguageConfig(code="cs", name="Czech", valid_diacritics=set("čšž"), allowed_anomalous_tokens={"SQL"})
        self.assertNotIn("Č", cfg.conflicting_diacritics)
        self.assertIn("sql", cfg.allowed_anomalous_tokens)

    def test_quality_misc_edge_cases(self) -> None:
        self.assertIsNone(normalize_layer_name("   "))
        mat = MaterializedVerificationResult.from_dict({"document_id": "d1", "layer_scores": None, "violations": [{"violation_id": "v1"}]})
        self.assertEqual(mat.layer_scores, {})
        self.assertEqual(mat.total_violations, 1)

        self.assertEqual(compute_grid_consistency([["Item", 2], ["Pen", 3]]), 1.0)
        failures = check_table_assertion([["Item", "Qty"], ["Pen", 2]], TableAssertion(numeric_column_indices=[5]))
        self.assertEqual(len(failures), 1)

    def test_table_and_docling_and_ocr_parser_fixes(self) -> None:
        zero_tbl = parse_table_content({"rows": [["A", "B"], ["1", "2"]], "cell_alignment_score": 0.0})
        self.assertEqual(zero_tbl["cell_alignment_score"], 0.0)

        one_row_md = parse_markdown_table("| ColA | ColB |\n| --- | --- |")
        self.assertEqual(one_row_md.markdown_table.count("ColA"), 1)

        def cell(txt: str, hdr: bool = False, col_span: int = 1) -> SimpleNamespace:
            return SimpleNamespace(text=txt, column_header=hdr, row_span=1, col_span=col_span)
        grid = [
            [cell("Banner Title", col_span=2), cell("Banner Title", col_span=2)],
            [cell("Header A", hdr=True), cell("Header B", hdr=True)],
            [cell("v1"), cell("v2")],
        ]
        item = SimpleNamespace(data=SimpleNamespace(num_rows=3, num_cols=2, grid=grid), label="table")
        parsed_docling = parse_docling_table(item)
        self.assertEqual(parsed_docling.title, "Banner Title")
        self.assertEqual(parsed_docling.num_rows, 2)
        self.assertEqual(len(parsed_docling.grid), 2)
        self.assertEqual(parsed_docling.grid[0][0]["row_idx"], 0)

        # Docling helpers: word-boundary deep OCR and partial provenance
        deep_content = build_node_content(SimpleNamespace(text="Zapytanie sql oraz q w faq"), "paragraph", preset="docling_deep", language="pl")
        self.assertEqual(deep_content["raw_text"], "Zapytanie sql oraz ą w faq")

        bbox_conv = fallback_top_left_bbox(SimpleNamespace(l=0.0, t=100.0, r=50.0, b=50.0, coord_origin="bottom_left"), 792.0)
        self.assertEqual(bbox_conv, (0.0, 692.0, 50.0, 742.0))
        p_no, x0, y0, x1, y1 = extract_page_no_and_bbox(None, object(), SimpleNamespace(page_no=3, bbox=None))  # type: ignore[arg-type]
        self.assertEqual((p_no, x0, y0, x1, y1), (3, 0.0, 0.0, 0.0, 0.0))

        # OCR flags, imaging, bbox, pypdfium, section_ocr
        flags = parse_ocr_custom_flags("tessedit_char_whitelist=0,1,2,3")
        self.assertEqual(flags["whitelist"], "0,1,2,3")

        pil_gray = normalize_to_pil(np.zeros((16, 16, 1), dtype=np.float32))
        self.assertEqual(pil_gray.size, (16, 16))
        self.assertEqual(normalize_bbox_coords(np.array([1.0, 2.0, 30.0, 40.0])), (1.0, 2.0, 30.0, 40.0))
        flat_bb = _convert_ocr_box_to_bbox([10.0, 20.0, 100.0, 60.0], 2.0, 2.0, 612.0, 792.0)
        self.assertEqual((flat_bb.x0, flat_bb.y0, flat_bb.x1, flat_bb.y1), (5.0, 10.0, 50.0, 30.0))

        sec = SectionOCRParser(language="en")
        txt, conf, lines = sec._parse_engine_result([([[0, 0], [10, 0], [10, 10], [0, 10]], ("Hello", np.float32(0.95)))])
        self.assertEqual(txt, "Hello")
        self.assertAlmostEqual(conf, 0.95, places=3)
        self.assertEqual(len(lines), 1)
        self.assertEqual(sec._parse_engine_result({"text": None, "confidence": None}), ("", 1.0, []))

        cli_fn = sec._create_cli_subprocess_engine(
            ["echo_tool", "{input_path}", "--psm", "{psm}"],
            wiggle_parameters=[ParameterWiggleSpec(name="psm", default_value="6")],
        )
        with patch("src.parsers.section_ocr.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            cli_fn(np.zeros((10, 10, 3), dtype=np.uint8))
            called_cmd = mock_run.call_args.args[0]
            self.assertEqual(called_cmd[-2:], ["--psm", "6"])

        dom_explicit = convert_dom_dict_to_dom(
            {"total_pages": 4, "nodes": [{"node_id": "n1", "global_page_index": 1, "temp_slice_index": 1}]},
            resolved_path="sample.pdf",
        )
        self.assertEqual(dom_explicit.total_pages, 4)

    def test_server_cache_mappings_and_viewer_html_fixes(self) -> None:
        self.assertEqual(parse_run_dir_and_step(None), ("", None))

        run_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(run_dir, exist_ok=True)
        with open(os.path.join(run_dir, "document_dom.json"), "w", encoding="utf-8") as fp:
            json.dump({"document_id": "d1", "source_filename": "sample.pdf", "total_pages": 1, "nodes": []}, fp)
        with open(os.path.join(run_dir, "decision_tree.json"), "w", encoding="utf-8") as fp:
            json.dump({"chosen_preset": "docling_deep", "overall_confidence": 0.95, "status": "ACCEPT"}, fp)

        cache = PresetCache()
        prev_runs = [{"id": "output:step_1", "dir_path": "output", "chosen_preset": "docling_fast", "document_name": "sample.pdf"}]
        self.assertIsNone(cache.find_in_previous_runs("sample.pdf", "docling_fast", prev_runs, self.temp_dir))

        register_document_path("src/e2e/sample_reg.pdf", repo_root=self.temp_dir)
        persisted = load_persistent_mappings(self.temp_dir)
        self.assertEqual(persisted["src/e2e/sample_reg.pdf"]["file_name"], "sample_reg.pdf")

        doc_mappings = {
            "src/e2e/sample_reg.pdf": {
                "file_path": "src/e2e/sample_reg.pdf",
                "file_name": "sample_reg.pdf",
                "file_set": "e2e",
                "runs": [],
            }
        }
        merge_persistent_runs(
            doc_mappings,
            {"sample_reg.pdf": {"runs": [{"run_id": "run_x", "output_dir": "output/run_x", "preset": "docling_fast"}]}},
            removed_runs=set(),
            repo_root=self.temp_dir,
        )
        self.assertEqual(len(doc_mappings["src/e2e/sample_reg.pdf"]["runs"]), 1)

        dom = make_test_dom("Script test </script><script>alert(1)</script>", document_id="d_xss", source_filename="xss.pdf")
        html_out = build_viewer_html(
            dom=dom,
            decision={"overall_confidence": None, "status": "ACCEPT"},
            violations=[],
            img_data_uri="data:image/png;base64,",
        )
        self.assertNotIn("</script><script>alert(1)</script>", html_out)
        self.assertIn("<\\/script><script>alert(1)<\\/script>", html_out)


if __name__ == "__main__":
    unittest.main()
