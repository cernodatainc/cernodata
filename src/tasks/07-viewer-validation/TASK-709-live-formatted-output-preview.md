# TASK-709: Live formatted output preview in the viewer

Depends on: TASK-704

When editing DOM node types, decolliding boxes, or adjusting reading order in `/viewer`, users currently cannot observe how the final structured output (such as clean Markdown or hierarchical RAG chunks) will be rendered downstream until they finish and export. This lack of feedback makes it difficult to verify whether section headings nest correctly or whether table content aligns with surrounding text.

- Add a "Live Output" tab (`outputTab`) to `src/visualization/viewer/html/inspector.html` alongside the DOM and Violations tabs.
- Create `src/visualization/viewer/js/live_output.js` (and register it in `JS_MODULE_ORDER` in `src/visualization/viewer/scripts.py`):
  - Formats the current page's (or document's) `domData.nodes` into rendered Markdown and raw formatted text in active reading order.
  - Subscribes to changes in `domData.nodes` (type switches, text updates, node deletion, splitting, and reordering) and automatically updates the preview pane.
  - Adds bidirectional hover interactions: hovering over a rendered paragraph, heading, or table block highlights its corresponding bounding box polygon on the canvas and card in the DOM tree.
