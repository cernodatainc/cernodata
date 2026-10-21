# TASK-706: Keyboard violation jumping, node approval, and text search in the viewer

Reviewing a 50-page document with the mouse takes too many clicks when only a handful of nodes have quality violations.

Create `src/visualization/viewer/js/review_navigation.js` (and register it in `src/visualization/viewer/scripts.py`, hooking into `selectNode` in `src/visualization/viewer/js/inspector.js`):

- Bind `]` and `[` (plus Next/Prev Violation buttons in `src/visualization/viewer/html/inspector.html`) to jump directly to the next or previous node across all pages that has an active quality violation or `is_incorrect_text` flag.
- Bind `v` (when not typing in an input) to accept/approve the currently selected node's active violations (`toggleSuppressSingleViolation`) and advance to the next flagged node.
- Add a search input at the top of `src/visualization/viewer/html/inspector.html` that filters the DOM list by matching text across all pages and jumps to the clicked node.
