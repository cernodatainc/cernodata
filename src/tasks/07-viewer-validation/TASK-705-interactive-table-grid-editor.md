# TASK-705: Interactive table grid editor in the viewer

Depends on: TASK-701

When a `table_grid` node is selected in the viewer (`src/visualization/viewer/js/inspector_components.js:211`), the user only gets a raw `<textarea>` full of pipe-delimited text. Editing a multi-column table in a small plain-text box is awkward and easy to break.

- Create `src/visualization/viewer/js/table_editor.js` (and register it in `src/visualization/viewer/scripts.py`):
  - Parse `node.content.markdown_table` (or `raw_text`) into a 2D array of cells.
  - Render an editable HTML `<table>` with cell inputs plus buttons to add/remove a row or column and a toggle to switch back to raw text.
  - Sync cell edits back into `node.content.markdown_table` and `node.content.raw_text`.
- Mount this grid editor inside `renderSingleNodeEditorComponent` (`src/visualization/viewer/js/inspector_components.js` at `TODO(TASK-705)`) whenever `node.type === "table_grid"`.
