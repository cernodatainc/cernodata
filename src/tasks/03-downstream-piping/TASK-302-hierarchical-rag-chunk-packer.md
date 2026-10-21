# TASK-302: Hierarchical RAG chunk packer (`JSONL`)

Raw `DocumentDOM` nodes are often too small (a single short paragraph detached from its heading) or too large for embedding models. Vector RAG tools need a `.jsonl` export where each chunk carries its section heading path and tables aren't sliced in half (`data_storage_decision_tree.md` Section 2).

Create `src/pipeline/exporters/rag_chunk_packer.py` and wire it into `export_rag_chunks_artifact` in `src/pipeline/artifact_exporter.py`:

- Traverse `dom.nodes` in reading order while tracking the current `heading` hierarchy.
- Prepend the active heading path (`"[Section: <Heading>] "`) to each packed chunk so isolated paragraphs keep their context.
- Keep `table_grid` nodes together in a single chunk whenever `len(table_text) <= max_chars`, keeping any preceding caption attached.
- Emit newline-delimited JSON objects with `chunk_id`, `doc_id`, `text`, `header_path`, `page_indices`, `node_ids`, and `ocr_confidence`.

Add unit tests in `src/tests/test_rag_chunk_packer.py`.
