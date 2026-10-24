# TASK-109: Ground-truth Q&A benchmark pairs for retrieval testing

To verify that our retrieval evaluator (`TASK-105`, `TASK-106`) catches real parsing mistakes, we need a small set of sample documents paired with questions that specifically break when layout parsing goes wrong (for example, when table columns get scrambled, footnotes get merged into body text, or section headings get detached from their paragraphs).

Create `src/tests/fixtures/retrieval_benchmark/` containing:

1. Three short synthetic documents (`doc_pricing_matrix.md`, `doc_safety_protocol.md`, `doc_annual_summary.md`) with multi-column tables, footnotes that modify numbers in the table, and warning callouts.
2. `benchmark_questions.json` with 12-15 test questions:
   - `question`: the question a user would ask.
   - `expected_answer_substrings`: exact numbers or phrases that must appear in the retrieved chunk.
   - `expected_source_docs`: which file contains the answer.
   - `failure_mode_tested`: what parsing bug would cause this question to fail (e.g. `"row_merge_in_table"`, `"detached_section_header"`, `"lost_footnote"`).
