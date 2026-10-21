# TASK-601: Multi-document corpus scanner and manifest

The pipeline currently runs on one PDF at a time. To notice when a user provides an imbalanced document set (such as 100 files on Topic A and 10,000 files on Topic B), we first need a scanner that inventories a folder of PDFs or parsed `document_dom.json` files.

Create `src/pipeline/corpus/__init__.py` and `src/pipeline/corpus/manifest.py`:

- `CorpusDocumentEntry`: `doc_id`, `source_path`, `subfolder_tag` (parent folder name if inside a subfolder), `page_count`, `total_chars`, `node_count`, and `assigned_topic: Optional[str] = None`.
- `CorpusManifest`:
  - `total_documents: int`
  - `entries: list[CorpusDocumentEntry]`
  - `scan_directory(input_dir: str) -> CorpusManifest`: recursively finds PDFs and existing `document_dom.json` files in deterministic order.

Add unit tests in `src/tests/test_corpus_manifest.py`.
