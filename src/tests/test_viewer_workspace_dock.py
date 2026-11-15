"""
src/tests/test_viewer_workspace_dock.py

Unit tests for node viewer folding/unanchoring, draggable toolboxes,
and keystroke hint badge overlay in the interactive viewer.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

from src.visualization.viewer.scripts import bundle_viewer_js


class TestViewerWorkspaceDock(unittest.TestCase):
    """Tests workspace dock JS runtime and CSS/HTML integration."""

    def test_workspace_dock_runtime_in_node(self) -> None:
        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("node binary not available")

        js_code = bundle_viewer_js()
        test_harness = (
            """
const assert = require('assert');
global.window = global;
global.window.addEventListener = () => {};
global.window.innerWidth = 1280;
global.window.innerHeight = 800;
global.window.location = { search: '', pathname: '/viewer.html' };
global.navigator = {};

function makeMockEl(id) {
    const classes = new Set();
    return {
        id,
        style: {},
        textContent: '',
        title: '',
        checked: false,
        parentNode: null,
        classList: {
            add: (...c) => c.forEach(x => classes.add(x)),
            remove: (...c) => c.forEach(x => classes.delete(x)),
            toggle: (c, force) => {
                const next = (force !== undefined) ? Boolean(force) : !classes.has(c);
                if (next) classes.add(c); else classes.delete(c);
                return next;
            },
            contains: (c) => classes.has(c)
        },
        querySelector: () => null,
        getBoundingClientRect: () => ({ left: 40, top: 80, width: 300, height: 40 })
    };
}

const mockEls = {
    inspectorPane: makeMockEl('inspectorPane'),
    btnFoldInspector: makeMockEl('btnFoldInspector'),
    btnAnchorInspector: makeMockEl('btnAnchorInspector'),
    toolboxNav: makeMockEl('toolboxNav'),
    toggleKeyHints: makeMockEl('toggleKeyHints')
};
const bodyClasses = new Set();

global.document = {
    readyState: 'complete',
    getElementById: (id) => mockEls[id] || null,
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener: () => {},
    createElement: () => ({ style: {}, classList: { add: () => {}, remove: () => {} }, appendChild: () => {} }),
    body: {
        appendChild: () => {},
        classList: {
            toggle: (c, force) => {
                const next = (force !== undefined) ? Boolean(force) : !bodyClasses.has(c);
                if (next) bodyClasses.add(c); else bodyClasses.delete(c);
                return next;
            },
            contains: (c) => bodyClasses.has(c)
        }
    }
};

"""
            + js_code
            + """

assert.strictEqual(toggleInspectorFold(), true);
assert.strictEqual(mockEls.inspectorPane.classList.contains('folded'), true);
assert.strictEqual(mockEls.btnFoldInspector.textContent, 'Unfold');
assert.strictEqual(toggleInspectorFold(), false);
assert.strictEqual(mockEls.inspectorPane.classList.contains('folded'), false);

assert.strictEqual(toggleInspectorAnchor(), true);
assert.strictEqual(mockEls.inspectorPane.classList.contains('unanchored'), true);
assert.strictEqual(mockEls.btnAnchorInspector.textContent, 'Dock');
assert.strictEqual(toggleInspectorAnchor(), false);
assert.strictEqual(mockEls.inspectorPane.classList.contains('unanchored'), false);

assert.strictEqual(toggleToolboxAnchor('toolboxNav'), true);
assert.strictEqual(mockEls.toolboxNav.classList.contains('unanchored'), true);
assert.strictEqual(toggleToolboxAnchor('toolboxNav'), false);
assert.strictEqual(mockEls.toolboxNav.classList.contains('unanchored'), false);

assert.strictEqual(updateKeyHintsOverlay(true), true);
assert.strictEqual(bodyClasses.has('show-key-hints'), true);
assert.strictEqual(updateKeyHintsOverlay(false), false);
assert.strictEqual(bodyClasses.has('show-key-hints'), false);
"""
        )
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tmp:
            tmp.write(test_harness)
            tmp_path = tmp.name
        try:
            res = subprocess.run([node_bin, tmp_path], capture_output=True, text=True, timeout=10)
            self.assertEqual(res.returncode, 0, f"Workspace dock runtime test failed:\n{res.stderr}\n{res.stdout}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
