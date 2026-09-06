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


if __name__ == "__main__":
    unittest.main()
