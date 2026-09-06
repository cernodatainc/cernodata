"""
src/test_pipeline.py

Comprehensive unit test suite for modular src/ pipeline components:
dom, converter, heuristics, decision_tree, and visualizer.
"""

import os
import json
import unittest
from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.converter import DoclingParser
from src.heuristics import compute_garbage_ratio, compute_language_score, evaluate_page_confidence, detect_quality_violations
from src.decision_tree import DecisionTreeEngine
from src.visualizer import PageVisualizer
from src.main import run_pipeline


class TestCernodataPipeline(unittest.TestCase):

    def test_dom_serialization(self):
        bbox = BoundingBox(10.0, 20.0, 100.0, 200.0)
        node = DOMNode(
            node_id="node_1",
            type="heading",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=bbox,
            content={"raw_text": "Sample Title"}
        )
        dom = DocumentDOM(document_id="doc_1", source_filename="test.pdf", total_pages=1, nodes=[node])
        dom_dict = dom.to_dict()

        self.assertEqual(dom_dict["document_id"], "doc_1")
        self.assertEqual(len(dom_dict["nodes"]), 1)
        self.assertEqual(dom_dict["nodes"][0]["bounding_box"]["x0"], 10.0)

    def test_garbage_ratio_and_confidence(self):
        self.assertEqual(compute_garbage_ratio("Clean Text"), 0.0)
        dirty_text = "Clean\x00\x01\x02Text"
        self.assertGreater(compute_garbage_ratio(dirty_text), 0.0)

        node = DOMNode(
            node_id="n1", type="paragraph", global_page_index=1, temp_slice_index=1,
            bounding_box=BoundingBox(0, 0, 10, 10), content={"raw_text": "Normal text"}
        )
        conf = evaluate_page_confidence([node])
        self.assertEqual(conf, 1.0)

    def test_polish_language_diacritic_anomaly_detection(self):
        clean_pl_text = "Sprawdź termin wykupu swoich obligacji i zamień je na nowe w piątku."
        pl_score_clean = compute_language_score(clean_pl_text, language="pl")
        self.assertEqual(pl_score_clean, 1.0)

        corrupted_pl_text = "Sprawdź termin wykupu swoich obligacji i zamień je na nowe w piqtku."
        pl_score_corrupted = compute_language_score(corrupted_pl_text, language="pl")
        self.assertLess(pl_score_corrupted, 1.0)

    def test_detect_quality_violations(self):
        node = DOMNode(
            node_id="n_viol", type="paragraph", global_page_index=1, temp_slice_index=1,
            bounding_box=BoundingBox(10, 10, 100, 50),
            content={"raw_text": "Infolinia czynna w piqtku."}
        )
        dom = DocumentDOM(document_id="doc_viol", source_filename="sample.pdf", total_pages=1, nodes=[node])

        violations = detect_quality_violations(dom, language="pl")
        self.assertEqual(len(violations), 1)
        v = violations[0]
        self.assertEqual(v["detected_snippet"], "piqtku")
        self.assertEqual(v["suggested_correction"], "piątku")
        self.assertEqual(v["rule_type"], "ocr_character_substitution")

    def test_decision_tree_engine_with_language_hint(self):
        node = DOMNode(
            node_id="n1", type="paragraph", global_page_index=1, temp_slice_index=1,
            bounding_box=BoundingBox(0, 0, 10, 10), content={"raw_text": "Sprawdź termin wykupu w piqtku."}
        )
        dom = DocumentDOM(document_id="doc_test", source_filename="sample.pdf", total_pages=1, nodes=[node])

        engine = DecisionTreeEngine(target_threshold=0.90, language="pl")
        res = engine.evaluate(dom)
        self.assertEqual(res["status"], "TRIGGER_FALLBACK")
        self.assertIn("ocr_language_hint", res["decision_tree"]["recommended_parameter_adjustments"])

    def test_visualizer_rendering_with_violations(self):
        node = DOMNode(
            node_id="n1", type="heading", global_page_index=1, temp_slice_index=1,
            bounding_box=BoundingBox(50, 50, 400, 100), content={"raw_text": "Infolinia czynna w piqtku"}
        )
        dom = DocumentDOM(document_id="doc_vis", source_filename="sample.pdf", total_pages=1, nodes=[node])
        violations = detect_quality_violations(dom, language="pl")

        visualizer = PageVisualizer(dpi=72)
        out_paths = visualizer.render_overlay("non_existent.pdf", dom, violations=violations, output_dir="test_output")
        self.assertGreater(len(out_paths), 0)
        self.assertTrue(os.path.exists(out_paths[0]))

        if os.path.exists(out_paths[0]):
            os.remove(out_paths[0])


if __name__ == "__main__":
    unittest.main()
