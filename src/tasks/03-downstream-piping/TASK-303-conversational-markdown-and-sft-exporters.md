# TASK-303: Clean Markdown and SFT JSONL exporters

Users feeding parsed documents into a chat prompt or a fine-tuning tool need clean Markdown or filtered `.jsonl` rather than bounding-box JSON (`data_storage_decision_tree.md` Sections 1.B and 1.C).

Create `src/pipeline/exporters/markdown_exporter.py` and wire it into `export_markdown_and_sft_artifacts` in `src/pipeline/artifact_exporter.py`:

- `export_clean_markdown(dom: DocumentDOM, min_confidence: float = 0.0, include_xml_wrapper: bool = False) -> str`: formats `heading` nodes as `#`/`##`, `table_grid` nodes as Markdown tables, `figure` nodes with their caption, and optionally wraps the document in `<document>` tags.
- `export_sft_pretraining_jsonl(dom: DocumentDOM, min_confidence: float = 0.85) -> str`: drops `header_footer` nodes and any node whose confidence is below `min_confidence` (or that has active quality violations), emitting `{"doc_id": ..., "text": ...}` lines.

Add unit tests in `src/tests/test_markdown_exporter.py`.
