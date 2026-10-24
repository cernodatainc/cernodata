# TASK-701: Single-node type switcher in the viewer inspector

In `src/visualization/viewer/js/inspector_components.js:187` (`renderSingleNodeEditorComponent`), a selected node's type (`heading`, `paragraph`, `table_grid`, `figure`, `header_footer`) is rendered as plain text:
```html
<h4>Selected: ${escapeHtml(node.node_id)} (${escapeHtml(node.type)})</h4>
```
Users can currently only change a node's type when merging two nodes in `decollide_components.js`, so there is no way to fix a heading that was misclassified as a paragraph on a single box.

- In `renderSingleNodeEditorComponent` (`src/visualization/viewer/js/inspector_components.js`), replace the static `(${escapeHtml(node.type)})` label with a `<select>` dropdown listing all `DOMNodeType` values (`paragraph`, `heading`, `table_grid`, `figure`, `header_footer`, `multi_column_group`).
- Add a handler in `src/visualization/viewer/js/inspector.js` that updates `node.type`, re-renders the DOM tree card and SVG overlay box color, and persists or marks the change in `computeDomDiff()`.
