# TASK-703: Viewer undo and redo stack (`Ctrl+Z` / `Ctrl+Y`)

If a user accidentally deletes a box, merges the wrong pair of boxes, or drags a resize handle too far in the viewer, there is currently no single-step Undo (`[REVERT] Revert to Raw` wipes out all edits on the document).

- Create `src/visualization/viewer/js/history.js` (and include it in `src/visualization/viewer/scripts.py`) maintaining a bounded history stack (up to 50 snapshots of `domData.nodes` and `violationsData`).
- Call `pushHistorySnapshot()` before node deletion (`deleteDOMNode` in `src/visualization/viewer/js/inspector.js`), node merge/unmerge (`decollide.js`), coordinate edits, and box creation.
- Add Undo and Redo buttons to `src/visualization/viewer/html/toolbar.html` and bind `Ctrl+Z` / `Ctrl+Y` when focus is not inside a text input.
