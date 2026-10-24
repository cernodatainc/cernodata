# TASK-502: Company letterhead and repeating header/footer stripper

Depends on: TASK-501

Corporate PDFs (memos, contracts, SOPs, invoices) usually have a company letterhead at the top of page 1 and repeating headers or footers across every page (e.g. `"ACME Corp - Confidential | Page 4 of 22"`). When left in, these pollute RAG chunks and interrupt paragraphs that cross page breaks.

Create `src/pipeline/postprocessors/letterhead_stripper.py` implementing `CompanyHeaderFooterStripper`:

- Detect nodes in the top 12% or bottom 12% of pages whose text (ignoring digits) repeats across at least half the pages in a multi-page document.
- Strip nodes classified as `header_footer` (`src/dom/enums.py`) or matching company letterhead patterns (address/registration blocks in top/bottom margins, `"Page X of Y"`, ISO document control headers from `TASK-507`).
- Record each stripped node in `PostprocessActionRecord` (including `original_node_dict`) so the user can still inspect or restore it in the viewer.

Add unit tests in `src/tests/test_letterhead_stripper.py`.
