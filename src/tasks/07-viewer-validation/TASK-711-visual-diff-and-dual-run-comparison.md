# TASK-711: Visual diff and dual-run comparison in the viewer

When validating fallback presets or reviewing manual edits against pristine raw extraction output, users need to see exactly where bounding boxes, text content, and node classifications diverged without comparing raw JSON files or switching between browser tabs.

- Add a "Diff Overlay" button to `src/visualization/viewer/html/toolbar.html` (at `TODO(TASK-711)`).
- Create `src/visualization/viewer/js/visual_diff.js` (and register it in `JS_MODULE_ORDER` in `src/visualization/viewer/scripts.py`):
  - Renders visual diff overlays directly on the viewer canvas: green bounding borders for added nodes, red borders with diagonal crosshatch for deleted nodes, and amber borders for modified boxes and altered text content.
  - Computes or consumes `computeDomDiff()` and `run_diff.json` to summarize modifications, additions, and deletions per page.
  - Supports side-by-side split canvas mode comparing two selected pipeline run output directories or pristine raw DOM versus current annotations.
  - Adds an interactive diff inspector drawer listing all modified nodes with inline word/character diffs and jump-to-node links.
