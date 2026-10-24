# TASK-405: Ollama document summary and table metadata enrichment

Depends on: TASK-401

RAG search and fine-tuning exports work much better when documents have a short summary, domain keywords, and plain-English explanations of numeric tables (`data_storage_decision_tree.md` Sections 1.A and 1.B).

Create `src/pipeline/ollama_enricher.py`:

- `enrich_document_metadata(dom: DocumentDOM, client: OllamaClient, model: str = "qwen2.5:3b", enrich_tables: bool = True) -> DocumentDOM`:
  - Generates a 2-3 sentence summary, 5-10 keywords, and a detected domain tag, storing them on the document.
  - When `enrich_tables=True`, generates a short natural-language description for each `table_grid` node (`node.content["table_summary"]`) so semantic search can match narrative queries against numeric tables.
- Add `ollama_enrich_model: Optional[str] = None` to `IngestionConfig` (`src/pipeline/planner/models.py`).

Add unit tests in `src/tests/test_ollama_enricher.py`.
