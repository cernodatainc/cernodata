# TASK-707: Direct formatted export from the viewer toolbar

Depends on: TASK-302, TASK-303

Once a user finishes fixing boxes, headings, and tables in `/viewer` and saves their annotations, they shouldn't have to switch back to another screen to get their final Markdown or JSONL file.

- Add an `"Export As..."` dropdown (`Clean Markdown`, `RAG Chunks (.jsonl)`, `Fine-Tuning Dataset (.jsonl)`, `DOM JSON`) to `src/visualization/viewer/html/toolbar.html`.
- When clicked, call `saveAnnotations(true)` first so any unsaved edits are persisted, then download the selected format from `GET /api/export` (`src/pipeline/server/routes/persistence.py`, using the exporters from `TASK-302` and `TASK-303`).
- Add a `"Copy Page as Markdown"` button for quick clipboard inspection.
