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
            self.assertIn("renderCutoutPreview", content)
            self.assertIn("cutout-preview-card", content)
            self.assertIn("triggerCutoutSecondPass", content)
            self.assertIn("toggleCutoutUnskew", content)
            self.assertIn("getEffectiveNodeAngle", content)
            self.assertIn("inpAngle", content)
            self.assertIn("renderTriangleWarp", content)
            self.assertIn("getNodeSkewCorners", content)
            self.assertIn("btnPrevPage", content)
            self.assertIn("btnNextPage", content)
            self.assertIn("pageSelect", content)
            self.assertIn("switchPage", content)
            self.assertIn("totalPages", content)
            self.assertIn("pageImages", content)
            self.assertIn("selected-violations-box", content)
            self.assertIn("applySingleFix", content)
            self.assertIn("(showViol || isSelected)", content)
            self.assertIn("apply-fix-btn", content)
            self.assertIn("mergeDOMNodes", content)
            self.assertIn("executeMergeElements", content)
            self.assertIn("btnMergeElements", content)
            self.assertIn("mergeTargetType", content)
            self.assertIn("mergeContentAction", content)
            self.assertIn("showAllDomNodes", content)
            self.assertIn("showAllViolations", content)
            self.assertIn("toggleShowAllDom", content)
            self.assertIn("toggleShowAllViolations", content)
            self.assertIn("tabBtnDom", content)
            self.assertIn("tabBtnViol", content)
            self.assertIn("tabBtnRuns", content)
            self.assertIn('data-name="dom page"', content)
            self.assertIn('data-name="violations"', content)
            self.assertIn("viol-bundle", content)
            self.assertIn("btn-accept-bundle", content)
            self.assertIn("acceptCategoryOnPage", content)
            self.assertIn("restoreCategoryOnPage", content)
            self.assertIn("toggleSuppressSingleViolation", content)
            self.assertIn("forceRerunFromViewerGrid", content)
            self.assertNotIn("btnRedoLang", content)
            self.assertNotIn("toggleCorrections", content)

        if os.path.exists(out_path):
            os.remove(out_path)

    def test_generate_interactive_html_multipage(self):
        nodes = [
            DOMNode(
                node_id="n1_p1", type="heading", global_page_index=1, temp_slice_index=1,
                bounding_box=BoundingBox(10, 10, 200, 50), content={"raw_text": "Page 1 Heading"}
            ),
            DOMNode(
                node_id="n2_p2", type="paragraph", global_page_index=2, temp_slice_index=2,
                bounding_box=BoundingBox(15, 15, 300, 80), content={"raw_text": "Page 2 Text"}
            ),
        ]
        dom = DocumentDOM(document_id="doc_multi", source_filename="Document 8.pdf", total_pages=2, nodes=nodes)
        pdf_path = os.path.join("src", "e2e", "Document 8.pdf")
        decision = {
            "chosen_preset": "docling_fast",
            "score": 90.0,
            "overall_confidence": 0.90,
            "per_page_confidence": {"1": 0.88, "2": 0.92},
            "status": "ACCEPT",
        }
        violations = []

        out_path = generate_interactive_html(
            pdf_path,
            dom=dom,
            decision=decision,
            violations=violations,
            output_path="test_output/test_multipage.html"
        )
        self.assertTrue(os.path.exists(out_path))

        with open(out_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Page 1 Heading", content)
            self.assertIn("Page 2 Text", content)
            self.assertIn("btnPrevPage", content)
            self.assertIn("btnNextPage", content)
            self.assertIn("data:image/png;base64,", content)
            self.assertIn("totalPages: 2", content)

        if os.path.exists(out_path):
            os.remove(out_path)


if __name__ == "__main__":
    unittest.main()
