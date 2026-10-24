# TASK-801: Single-page PDF slicer (`slice_pdf_pages`)

`Architecture_Specification.md` Section 4 and `parsing_decision_tree.md` Section 4 specify that if a 100-page PDF fails quality checks on page 42, only page 42 should be extracted into a temporary PDF and re-parsed by the heavier fallback model. Right now, `FallbackLoopHandler` (`src/pipeline/fallback_handler.py`) re-parses the entire PDF from page 1 on every retry.

Implement `slice_pdf_pages(pdf_path: str, page_indices: list[int], output_dir: str) -> str` in `src/parsers/pdf_utils.py`:

- Use `pypdfium2` (`PdfDocument.new()` and `import_pages`) to copy the requested 1-indexed `page_indices` into a temporary PDF file in `output_dir`.
- Raise `ValueError` or `IndexError` if `page_indices` is empty or out of bounds for the source document.

Add unit tests in `src/tests/test_pdf_slicer.py`.
