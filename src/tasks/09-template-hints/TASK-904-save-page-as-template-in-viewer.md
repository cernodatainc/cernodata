# TASK-904: Save current page layout as a template in the viewer

Depends on: TASK-901

Writing normalized `[0.0, 1.0]` bounding box coordinates by hand is tedious. Once a user has adjusted the boxes and node types on page 1 of a recurring form in `/viewer`, they should be able to save that page's layout as a reusable `DocumentTemplateHint` (`TASK-901`).

- Create `src/visualization/viewer/js/template_exporter.js` (and register it in `src/visualization/viewer/scripts.py`) with `saveCurrentPageAsTemplate()`:
  - Prompts for a template name/description.
  - Normalizes each node's bounding box on `currentPage` by the page dimensions (`x0 / pageWidth`, `y0 / pageHeight`, etc.).
  - POSTs the `DocumentTemplateHint` JSON to `POST /api/templates` (in `src/pipeline/server/routes/persistence.py`, saving to `output/templates/<template_id>.json`) and triggers a browser file download.
- Add a `"Save Page as Template"` button to `src/visualization/viewer/html/inspector.html`.
