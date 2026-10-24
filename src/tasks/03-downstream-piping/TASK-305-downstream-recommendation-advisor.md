# TASK-305: Downstream setup recommendation advisor

Depends on: TASK-302, TASK-303

Setting up external RAG databases or fine-tuning tools for the user is out of scope, but CernoData can inspect the parsed `DocumentDOM` and recommend which export format, chunk size, and external tools fit the user's stated goal (`data_storage_decision_tree.md` Sections 1 and 2).

Create `src/pipeline/exporters/downstream_advisor.py` and wire it into `build_downstream_recommendation` (`src/pipeline/artifact_exporter.py`) and `_build_downstream_setup_advice` (`src/pipeline/server/routes/planning.py`):

- Inspect the `DocumentDOM`: count total nodes, the proportion of `table_grid` nodes, average confidence score, and character volume.
- Return a dictionary with:
  - `recommended_export_format` (`"rag_jsonl"`, `"sft_jsonl"`, `"clean_markdown"`, or `"dom_json"`).
  - `recommended_chunk_size_chars` adjusted for table density and section length.
  - `hygiene_warnings` (for example, warning when low-confidence pages exist in a document intended for `slm_fine_tuning`).
  - `suggested_external_tools`: compatible tools for the chosen use case (e.g. AnythingLLM, OpenWebUI, Qdrant, Obsidian, Unsloth UI).

Add unit tests in `src/tests/test_downstream_advisor.py`.
