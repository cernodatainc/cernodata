# TASK-506: Web UI postprocessing checklist and viewer preview

Depends on: TASK-501, TASK-502, TASK-503, TASK-504, TASK-505

Give users visual checkboxes in the Web Hub (`src/visualization/landing.html`) and Interactive Viewer (`src/visualization/viewer/`) to turn postprocessing rules on or off and see what was stripped.

- Implement `initPostprocessingChecklistCard` in `src/visualization/landing/navigation.js` and add a "Document Cleanup & Postprocessing" card to `src/visualization/landing.html` with checkboxes for:
  - Strip company letterheads & repeating headers/footers (`TASK-502`)
  - Rejoin hyphenated words & split paragraphs (`TASK-503`)
  - Remove watermarks & stamps (`TASK-504`)
  - Redact emails, phone numbers, and IDs (`TASK-505`)
  - Custom phrases to strip
- Add `POST /api/postprocess` in `src/pipeline/server/routes/execution.py` so toggling a cleanup rule on an already-parsed document updates the DOM immediately without re-running OCR.
- Add a "Show Stripped Elements" toggle in `src/visualization/viewer/html/toolbar.html` so users can inspect stripped letterheads/watermarks in the viewer and restore any element with a click.

Add tests in `src/tests/test_ui_postprocessing.py`.
