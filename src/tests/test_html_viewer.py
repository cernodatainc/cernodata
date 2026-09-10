"""
src/tests/test_html_viewer.py

Unit tests for interactive HTML viewer generation.
"""

import os
import unittest
from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.quality import detect_quality_violations
from src.visualization.html_viewer import generate_interactive_html


class TestHTMLViewer(unittest.TestCase):

    def test_generate_interactive_html(self):
        node = DOMNode(
            node_id="n1", type="heading", global_page_index=1, temp_slice_index=1,
            bounding_box=BoundingBox(50, 50, 400, 100), content={"raw_text": "Test Heading"}
        )
        dom = DocumentDOM(document_id="doc_html", source_filename="sample.pdf", total_pages=1, nodes=[node])
        violations = detect_quality_violations(dom, language="pl")
        decision = {
            "chosen_preset": "docling_fast",
            "score": 85.5,
            "decision_log": ["Used fast preset", "Found 1 node"]
        }

        out_path = generate_interactive_html(
            "non_existent.pdf",
            dom=dom,
            decision=decision,
            violations=violations,
            output_path="test_output/test_interactive.html"
        )
        self.assertTrue(os.path.exists(out_path))
        
        with open(out_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Test Heading", content)
            self.assertIn("cernodata visual flow", content.lower())
            self.assertIn("selectLanguage", content)
            self.assertIn("Detected Lang:", content)
            self.assertIn("renderResizeHandles", content)
            self.assertIn("resize-handle", content)
            self.assertIn("toggleIncorrectText", content)
            self.assertIn("is_incorrect_text", content)
            self.assertIn("inpX0", content)
            self.assertIn("btnSaveAnnotations", content)
            self.assertIn("btnDecollidePage", content)
            self.assertIn("decollideCurrentPage", content)
            self.assertIn("decollideSelectedPair", content)
            self.assertIn("renderTwoNodeDecollideEditor", content)

        if os.path.exists(out_path):
            os.remove(out_path)


if __name__ == "__main__":
    unittest.main()
