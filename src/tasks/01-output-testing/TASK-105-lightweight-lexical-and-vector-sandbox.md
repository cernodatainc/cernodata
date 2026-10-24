# TASK-105: In-memory BM25 retrieval sandbox

To test whether a parsed set of `DocumentDOM` outputs can actually retrieve the chunk needed to answer a user's question (`testing_decision_tree.md` Section 5), we need a fast, zero-dependency retrieval index that runs in memory without external vector DB services.

Create `src/quality/retrieval_sandbox.py`:

- `IndexedChunk`: `chunk_id`, `doc_id`, `page_indices`, `node_ids`, `text`, and `tokens`.
- `LexicalRetrievalSandbox`:
  - `index_documents(documents: list[DocumentDOM], chunk_size_chars: int = 1000, chunk_overlap_chars: int = 150) -> None`: builds chunks from `DocumentDOM.nodes` in reading order, keeping the most recent `heading` node prepended to each chunk and keeping `table_grid` nodes intact when they fit within `chunk_size_chars`.
  - `query(question: str, top_k: int = 3) -> list[tuple[IndexedChunk, float]]`: scores chunks with BM25 ($k_1 = 1.5, b = 0.75$) using only Python's standard library (`math`, `re`, `collections.Counter`).

Add unit tests in `src/tests/test_retrieval_sandbox.py`.
