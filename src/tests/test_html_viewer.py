"""
src/tests/test_html_viewer.py

Unit tests for interactive HTML viewer generation.
"""

import os
import unittest
from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.quality import detect_quality_violations
from src.visualization.html_viewer import generate_interactive_html
from src.visualization.viewer.scripts import bundle_viewer_js


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
            self.assertIn("cernodata", content.lower())
            self.assertIn("onNodeTypeChange", content)
            self.assertIn("selectNodeType", content)
            self.assertIn("selectLanguage", content)
            self.assertIn("Detected language", content)
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
            self.assertIn("ViewerInputManager", content)
            self.assertIn("BaseInputLayer", content)
            self.assertIn("SelectInputLayer", content)
            self.assertIn("DrawSectionInputLayer", content)
            self.assertIn("RunDiffManager", content)
            self.assertIn("HistoryManager", content)
            self.assertIn("diffList", content)
            self.assertIn("recordRunDiff", content)
            self.assertIn("getActiveDiffs", content)
            self.assertIn("applyBackward", content)
            self.assertIn("applyForward", content)
            self.assertIn("active_diff_list", content)
            self.assertIn("diff_cursor", content)
            self.assertIn("undo", content)
            self.assertIn("redo", content)
            self.assertIn("btnUndo", content)
            self.assertIn("btnRedo", content)
            self.assertIn("moveNodeOrderUp", content)
            self.assertIn("moveNodeOrderDown", content)
            self.assertIn("selectNextViolation", content)
            self.assertIn("selectPreviousViolation", content)
            self.assertIn("showStatusBanner", content)
            self.assertIn("addDOMElement", content)
            self.assertIn("btnDrawSection", content)
            self.assertIn("btnInspectorDrawSection", content)
            self.assertNotIn("btnDrawSection\" hidden", content)
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

    def test_generate_interactive_html_with_table_node(self):
        table_node = DOMNode(
            node_id="table_1",
            type="table_grid",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(50, 100, 500, 300),
            content={
                "raw_text": "| Col 1 | Col 2 |\n| --- | --- |\n| Val 1 | Val 2 |",
                "rows": [["Col 1", "Col 2"], ["Val 1", "Val 2"]],
                "columns": [["Col 1", "Val 1"], ["Col 2", "Val 2"]],
                "headers": ["Col 1", "Col 2"],
                "num_rows": 2,
                "num_cols": 2,
                "markdown_table": "| Col 1 | Col 2 |\n| --- | --- |\n| Val 1 | Val 2 |",
                "cell_alignment_score": 1.0,
            },
        )
        dom = DocumentDOM(document_id="doc_table", source_filename="table_doc.pdf", total_pages=1, nodes=[table_node])
        decision = {"chosen_preset": "docling_fast", "score": 92.0, "decision_log": ["Table test"]}
        violations = []

        out_path = generate_interactive_html(
            "non_existent.pdf",
            dom=dom,
            decision=decision,
            violations=violations,
            output_path="test_output/test_table_modal.html",
        )
        self.assertTrue(os.path.exists(out_path))

        with open(out_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("openTableModal", content)
            self.assertIn("closeTableModal", content)
            self.assertIn("switchTableModalTab", content)
            self.assertIn("renderTableModal", content)
            self.assertIn("action-btn-view-table", content)
            self.assertIn("View Table Content", content)
            self.assertIn("table-modal-overlay", content)
            self.assertIn("table-modal-dialog", content)
            self.assertIn("table-modal-grid-table", content)
            self.assertIn("table-modal-grid-container", content)
            self.assertIn("chkTableModalAdvanced", content)
            self.assertIn("reparseTableModal", content)
            self.assertIn("chkOcrAdvanced", content)
            self.assertIn("toggleOcrAdvancedMode", content)
            self.assertIn("table_1", content)

        if os.path.exists(out_path):
            os.remove(out_path)

    def test_viewer_js_syntax_integrity(self):
        import shutil
        import subprocess
        import tempfile
        js_code = bundle_viewer_js()
        self.assertTrue(len(js_code) > 0)
        node_bin = shutil.which("node")
        if node_bin:
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tmp:
                tmp.write(js_code)
                tmp_path = tmp.name
            try:
                res = subprocess.run([node_bin, "--check", tmp_path], capture_output=True, text=True, timeout=10)
                self.assertEqual(res.returncode, 0, f"JS Syntax Error in bundled viewer.js:\n{res.stderr}")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

    def test_chapter7_viewer_components_present_and_rendered(self):
        dom = DocumentDOM(
            document_id="doc_ch7",
            source_filename="ch7.pdf",
            total_pages=1,
            nodes=[
                DOMNode(
                    node_id="tbl_ch7",
                    temp_slice_index=1,
                    global_page_index=1,
                    type="table_grid",
                    bounding_box=BoundingBox(10.0, 20.0, 210.0, 120.0),
                    content={
                        "rows": [["Title", "Title"], ["Key", "Value"], ["A", "1"]],
                        "headers": ["Key", "Value"],
                        "raw_text": "Key;Value\nA;1",
                        "num_rows": 3,
                        "num_cols": 2,
                    },
                )
            ],
        )
        out_path = generate_interactive_html(
            "non_existent.pdf",
            dom=dom,
            decision={"chosen_preset": "docling_fast", "overall_confidence": 0.9},
            violations=[],
            output_path="test_output/test_ch7_viewer.html",
        )
        self.assertTrue(os.path.exists(out_path))
        with open(out_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # TASK-704 card order controls
        self.assertIn("btn-order-up", html_content)
        self.assertIn("btn-order-down", html_content)
        # TASK-705 inline table editor
        self.assertIn("renderTableEditorComponent", html_content)
        self.assertIn("addTableRow", html_content)
        self.assertIn("addTableColumn", html_content)
        # TASK-707 advanced table re-parsing
        self.assertIn("applyTableReparseOptions", html_content)
        self.assertIn("parseTableCustomFlags", html_content)
        # TASK-709 Live Output tab
        self.assertIn("id=\"tabBtnOutput\"", html_content)
        self.assertIn("id=\"outputTab\"", html_content)
        self.assertIn("buildLiveOutputPayload", html_content)
        # TASK-710 Rule Tolerances drawer
        self.assertIn("id=\"btnRuleTolerances\"", html_content)
        self.assertIn("id=\"ruleTolerancesDrawer\"", html_content)
        self.assertIn("applyRuleTolerances", html_content)
        self.assertIn("isViolationInactive", html_content)
        # Undo/redo table snapshot & editor helpers
        self.assertIn("_applyNodeContentSnapshot", html_content)
        self.assertIn("_snapshotTableNode", html_content)
        # TASK-711 Diff Overlay toggle
        self.assertIn("id=\"btnDiffOverlay\"", html_content)
        self.assertIn("computeVisualDiffForPage", html_content)

        viewer_html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "visualization",
            "viewer",
            "viewer.html",
        )
        with open(viewer_html_path, "r", encoding="utf-8") as f:
            served_html = f.read()
        self.assertIn("id=\"tabBtnOutput\"", served_html)
        self.assertIn("id=\"btnRuleTolerances\"", served_html)
        self.assertIn("id=\"ruleTolerancesDrawer\"", served_html)
        self.assertIn("id=\"btnDiffOverlay\"", served_html)

        if os.path.exists(out_path):
            os.remove(out_path)


if __name__ == "__main__":
    unittest.main()
