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
            self.assertIn("if (showViol && nodeViols.length > 0)", content)
            self.assertNotIn("(showViol || isSelected)", content)
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
            self.assertNotIn("toggleBadges", content)
            self.assertNotIn("[ Viol", content)
            self.assertNotIn("Viol ]", content)
            self.assertIn("toolboxNav", content)
            self.assertIn("toolboxLayers", content)
            self.assertIn("toolboxLanguage", content)
            self.assertIn("toolboxEdit", content)
            self.assertIn("toolboxReview", content)
            self.assertIn("toggleToolboxAnchor", content)
            self.assertIn("toggleInspectorFold", content)
            self.assertIn("toggleInspectorAnchor", content)
            self.assertIn("toggleKeyHints", content)
            self.assertIn("updateKeyHintsOverlay", content)
            self.assertIn("data-key-hint", content)
            self.assertIn("show-key-hints", content)

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
        self.assertIn("id=\"btnPrevViol\"", served_html)
        self.assertIn("id=\"btnNextViol\"", served_html)
        self.assertIn("id=\"btnRevertRaw\"", served_html)
        self.assertIn("id=\"btnUndo\"", served_html)
        self.assertIn("id=\"btnRedo\"", served_html)
        self.assertIn("id=\"domSourceFilename\"", served_html)
        self.assertIn("id=\"domDocId\"", served_html)
        self.assertNotIn("toggleBadges", served_html)
        self.assertNotIn("[ Viol", served_html)
        self.assertNotIn("Viol ]", served_html)
        self.assertIn("id=\"inspectorPane\"", served_html)
        self.assertIn("id=\"btnFoldInspector\"", served_html)
        self.assertIn("id=\"btnAnchorInspector\"", served_html)
        self.assertIn("id=\"toggleKeyHints\"", served_html)
        self.assertIn("id=\"toolboxNav\"", served_html)
        self.assertIn("--ui-blue-bg", html_content)
        self.assertIn("--ui-blue-border", html_content)

        if os.path.exists(out_path):
            os.remove(out_path)

    def test_viewer_js_runtime_behavior_in_node(self):
        import shutil
        import subprocess
        import tempfile

        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("node binary not available")

        js_code = bundle_viewer_js()
        test_harness = """
const assert = require('assert');
global.window = global;
global.window.addEventListener = () => {};
global.document = {
    getElementById: () => null,
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener: () => {},
    createElement: () => ({ style: {}, classList: { add: () => {}, remove: () => {} }, appendChild: () => {} }),
    body: { appendChild: () => {} }
};
global.window.location = { search: '', pathname: '/viewer.html' };
global.navigator = {};

""" + js_code + """

// 1. Test renderDOMTreeNodeCardComponent does not throw ReferenceError
const cardHtml = renderDOMTreeNodeCardComponent(
    { node_id: 'n1', type: 'paragraph', is_merged: false },
    {
        nodePage: 1,
        isOnCurrentPage: true,
        isFixed: false,
        isIncorrect: false,
        hasActiveViol: false,
        hasSuppressedViol: false,
        displayText: 'Hello world',
        pageSeq: 1
    }
);
assert(cardHtml.includes('btn-order-up'), 'Expected btn-order-up in card HTML');
assert(cardHtml.includes('Hello world'), 'Expected displayText in card HTML');
assert(!INSPECTOR_PALETTE.bgCardHover.endsWith(';'), 'Expected no trailing semicolon in bgCardHover');

// 2. Test multi-page node reordering, undo/redo, and computeDomDiff
const initialNodes = [
    { node_id: 'p1_a', type: 'paragraph', global_page_index: 1, bounding_box: { x0: 0, y0: 0, x1: 10, y1: 10 }, content: { raw_text: 'A' } },
    { node_id: 'p2_x', type: 'paragraph', global_page_index: 2, bounding_box: { x0: 0, y0: 0, x1: 10, y1: 10 }, content: { raw_text: 'X' } },
    { node_id: 'p1_b', type: 'paragraph', global_page_index: 1, bounding_box: { x0: 0, y0: 20, x1: 10, y1: 30 }, content: { raw_text: 'B' } }
];
rawDomData = JSON.parse(JSON.stringify({ nodes: initialNodes }));
domData = JSON.parse(JSON.stringify({ nodes: initialNodes }));
window.runDiffManager.clear();

moveNodeOrderDown('p1_a');
assert.deepStrictEqual(
    domData.nodes.map(n => n.node_id),
    ['p1_b', 'p2_x', 'p1_a'],
    'Expected p1_a and p1_b to swap exact positions across intervening page 2 node'
);
const diffAfterReorder = computeDomDiff();
assert.strictEqual(diffAfterReorder.has_changes, true, 'Expected computeDomDiff().has_changes to be true after reorder');

undo();
assert.deepStrictEqual(
    domData.nodes.map(n => n.node_id),
    ['p1_a', 'p2_x', 'p1_b'],
    'Expected undo() to restore exact initial node order'
);

redo();
assert.deepStrictEqual(
    domData.nodes.map(n => n.node_id),
    ['p1_b', 'p2_x', 'p1_a'],
    'Expected redo() to re-apply exact node swap'
);

// 3. Test table reparse options (explicit header row 0 and keep banner) + escaped pipe parsing
const tblNode = {
    node_id: 'tbl_1',
    type: 'table_grid',
    global_page_index: 1,
    content: {
        rows: [['Banner', 'Banner'], ['ColA', 'ColB'], ['1', '2']],
        headers: ['Banner', 'Banner'],
        num_rows: 3,
        num_cols: 2
    }
};
applyTableReparseOptions(tblNode, '0', 'keep', '');
const extractedHdr0 = extractNodeTableData(tblNode);
assert.deepStrictEqual(extractedHdr0.headers, ['Banner', 'Banner'], 'Explicit header row 0 must not be overridden');

applyTableReparseOptions(tblNode, '1', 'keep', '');
const extractedKeep = extractNodeTableData(tblNode);
assert.deepStrictEqual(extractedKeep.headers, ['ColA', 'ColB'], 'Header row 1 should be ColA, ColB');
assert.strictEqual(extractedKeep.rows.length, 3, 'keep banner mode must retain all 3 rows in extractNodeTableData');
assert.strictEqual(extractedKeep.effectiveHdrIdx, 1, 'Effective header index must be 1');

const mdParsed = parseClientMarkdownTable('| A \\\\| B | C |\\n| --- | --- |\\n| 1 \\\\| 2 | 3 |');
assert.deepStrictEqual(mdParsed.headers, ['A | B', 'C'], 'Escaped pipes in headers must not split cells');
assert.deepStrictEqual(mdParsed.rows[1], ['1 | 2', '3'], 'Escaped pipes in rows must not split cells');

// 4. Test updateTableCell does not overwrite headers when editing a non-header row with identical values
domData.nodes = [{
    node_id: 'tbl_dup',
    type: 'table_grid',
    global_page_index: 1,
    content: {
        headers: ['X', 'Y'],
        rows: [['X', 'Y'], ['X', 'Y']],
        num_rows: 2,
        num_cols: 2
    }
}];
updateTableCell('tbl_dup', 1, 0, 'ChangedBody');
assert.deepStrictEqual(domData.nodes[0].content.headers, ['X', 'Y'], 'Editing body row 1 must not mutate table headers');
assert.strictEqual(domData.nodes[0].content.rows[1][0], 'ChangedBody');
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tmp:
            tmp.write(test_harness)
            tmp_path = tmp.name
        try:
            res = subprocess.run([node_bin, tmp_path], capture_output=True, text=True, timeout=10)
            self.assertEqual(res.returncode, 0, f"Viewer JS runtime test failed:\n{res.stderr}\n{res.stdout}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
