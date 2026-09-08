"""
src/tests/test_pipeline.py

Unit tests for DecisionTreeEngine and end-to-end orchestrator pipeline.
"""

import unittest
from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.pipeline import DecisionTreeEngine, run_pipeline


class TestPipelineEngine(unittest.TestCase):

    def test_decision_tree_engine_accept(self):
        node = DOMNode(
            node_id="n1", type="paragraph", global_page_index=1, temp_slice_index=1,
            bounding_box=BoundingBox(0, 0, 10, 10), content={"raw_text": "High quality text"}
        )
        dom = DocumentDOM(document_id="doc_test", source_filename="sample.pdf", total_pages=1, nodes=[node])

        engine = DecisionTreeEngine(target_threshold=0.82)
        res = engine.evaluate(dom)
        self.assertEqual(res["status"], "ACCEPT")
        self.assertTrue(res["is_accepted"])

    def test_decision_tree_engine_fallback(self):
        node = DOMNode(
            node_id="n1", type="paragraph", global_page_index=1, temp_slice_index=1,
            bounding_box=BoundingBox(0, 0, 10, 10), content={"raw_text": "Sprawdź termin wykupu w piqtku."}
        )
        dom = DocumentDOM(document_id="doc_test", source_filename="sample.pdf", total_pages=1, nodes=[node])

        engine = DecisionTreeEngine(target_threshold=0.90, language="pl")
        res = engine.evaluate(dom)
        self.assertEqual(res["status"], "TRIGGER_FALLBACK")
        self.assertIn("ocr_language_hint", res["decision_tree"]["recommended_parameter_adjustments"])


    def test_diacritic_hit_triggers_fallback(self):
        node = DOMNode(
            node_id="n1", type="paragraph", global_page_index=1, temp_slice_index=1,
            bounding_box=BoundingBox(0, 0, 10, 10), content={"raw_text": "Infolinia w piqtku."}
        )
        dom = DocumentDOM(document_id="doc_test", source_filename="sample.pdf", total_pages=1, nodes=[node])

        engine = DecisionTreeEngine(target_threshold=0.82, language="pl")
        res = engine.evaluate(dom)
        self.assertEqual(res["status"], "TRIGGER_FALLBACK")
        self.assertFalse(res["is_accepted"])
        self.assertLess(res["overall_confidence"], 0.82)

    def test_attempts_history_structure(self):
        from unittest.mock import patch

        node_bad = DOMNode(
            node_id="n1", type="paragraph", global_page_index=1, temp_slice_index=1,
            bounding_box=BoundingBox(0, 0, 10, 10), content={"raw_text": "piqtku w piqtku"}
        )
        dom_bad = DocumentDOM(document_id="doc_bad", source_filename="test.pdf", total_pages=1, nodes=[node_bad])

        node_good = DOMNode(
            node_id="n1", type="paragraph", global_page_index=1, temp_slice_index=1,
            bounding_box=BoundingBox(0, 0, 10, 10), content={"raw_text": "piątku w piątku"}
        )
        dom_good = DocumentDOM(document_id="doc_good", source_filename="test.pdf", total_pages=1, nodes=[node_good])

        with patch("src.pipeline.orchestrator.parse_document", side_effect=[dom_bad, dom_good]), \
             patch("src.pipeline.orchestrator.align_document_skew", side_effect=lambda d, p, a: d), \
             patch("src.pipeline.orchestrator.render_visual_overlays", return_value=[]), \
             patch("src.pipeline.orchestrator.export_pipeline_artifacts", return_value=("a.json", "b.json", "c.json")), \
             patch("src.pipeline.orchestrator.export_interactive_html_viewer", return_value="viewer.html"):

            res = run_pipeline(pdf_path="test.pdf", language="pl", preset="docling_fast")
            decision = res["decision"]
            self.assertIn("attempts", decision)
            attempts = decision["attempts"]
            self.assertEqual(len(attempts), 2)
            self.assertEqual(attempts[0]["step"], 1)
            self.assertEqual(attempts[0]["preset"], "docling_fast")
            self.assertEqual(attempts[0]["status"], "TRIGGER_FALLBACK")
            self.assertEqual(attempts[1]["step"], 2)
            self.assertEqual(attempts[1]["preset"], "docling_deep")
            self.assertEqual(attempts[1]["status"], "ACCEPT")
            self.assertIn("detail", attempts[1])


if __name__ == "__main__":
    unittest.main()
