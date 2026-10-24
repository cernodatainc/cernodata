# TASK-103: Real Markdown table grid validator

Depends on: TASK-101

In `src/parsers/docling_helpers.py:150`, table alignment scoring is currently faked with a hardcoded constant:
```python
content_dict["cell_alignment_score"] = 0.98 if preset == "docling_deep" else 0.96
```
And `src/quality/evaluator.py:89` reads that number with a `0.95` fallback. If a table has merged columns, ragged pipe counts across rows, or text in columns that should be numbers, the pipeline still scores it 0.96+.

Create `src/quality/table_validator.py` and replace the hardcoded score in `src/parsers/docling_helpers.py` and `src/quality/evaluator.py`:

- Parse `node.content.get("markdown_table")` or `raw_text` into rows and cells.
- Compute `cell_alignment_score` (`0.0` to `1.0`) from the fraction of rows whose column count matches the header row, penalizing empty header cells and ragged rows.
- When a `TableAssertion` (`TASK-101`) is provided, check `min_columns`, `min_rows`, `expected_column_headers`, and whether `numeric_column_indices` parse as numbers/currency, emitting a violation in `src/quality/violations.py` when a table fails.

Add unit tests in `src/tests/test_table_validator.py`.
