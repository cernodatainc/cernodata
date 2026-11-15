"""
src/tests/test_viewer_table_preview.py

Unit tests for table preview rendering in the DOM page node list.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

from src.visualization.viewer.scripts import bundle_viewer_js


class TestViewerTablePreview(unittest.TestCase):

    def test_table_node_card_renders_html_preview_in_node(self):
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

const tableCardHtml = renderDOMTreeNodeCardComponent(
    {
        node_id: 'tbl_md_only',
        type: 'table_grid',
        is_merged: false,
        content: {
            raw_text: '| Item | Qty |\\n| --- | --- |\\n| Apples | 3 |\\n| Pears | 5 |'
        }
    },
    {
        nodePage: 1,
        isOnCurrentPage: true,
        isFixed: false,
        isIncorrect: false,
        hasActiveViol: false,
        hasSuppressedViol: false,
        displayText: '| Item | Qty |\\n| --- | --- |\\n| Apples | 3 |\\n| Pears | 5 |',
        pageSeq: 2
    }
);
assert(tableCardHtml.includes('node-table-preview-table'), 'Expected HTML table preview in table_grid card');
assert(tableCardHtml.includes('<th>Item</th>') && tableCardHtml.includes('<td>Apples</td>'), 'Expected parsed header and cell in HTML table');
assert(!tableCardHtml.includes('| --- |'), 'Raw markdown separator must not be rendered on table_grid card');

const largeTableRows = [['H1', 'H2']];
for (let i = 1; i <= 7; i++) {
    largeTableRows.push([`R${i}`, `V${i}`]);
}
const largeTableCardHtml = renderDOMTreeNodeCardComponent(
    {
        node_id: 'tbl_large',
        type: 'table_grid',
        content: {
            headers: ['H1', 'H2'],
            rows: largeTableRows,
            num_rows: 8,
            num_cols: 2
        }
    },
    {
        nodePage: 1,
        isOnCurrentPage: true,
        isFixed: false,
        isIncorrect: false,
        hasActiveViol: false,
        hasSuppressedViol: false,
        displayText: '| H1 | H2 |',
        pageSeq: 3
    }
);
assert(largeTableCardHtml.includes('(+2 more)'), 'Expected truncation indicator for tables exceeding 5 data rows');
assert(!largeTableCardHtml.includes('<td>R6</td>'), 'Rows beyond preview cap should not be rendered in card');
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
