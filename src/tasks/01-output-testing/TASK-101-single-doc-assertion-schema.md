# TASK-101: Single-document assertion schema

Right now `src/quality/violations.py` only checks for generic OCR garbage and diacritic mistakes. Users need a way to state structural rules for a document (for example, "every document in this batch must have an `Abstract` and `References` heading" or "pages must contain at least one 3-column table").

Create `src/schemas/test_suite.py` with dataclasses that can be loaded from and saved to JSON:

- `HeaderAssertion`: expected heading text or regex, optional `case_sensitive` flag, and optional page bounds (`min_page`, `max_page`).
- `RegexAssertion`: pattern that must match (or must not match, via `must_match: bool`) within nodes of a given `DOMNodeType` (`src/dom/enums.py`), plus a minimum match count.
- `TableAssertion`: `min_columns`, `min_rows`, `expected_column_headers: list[str]`, and `numeric_column_indices: list[int]`.
- `DocumentAssertionSuite`: groups `required_headers`, `regex_rules`, `table_rules`, and `min_node_counts: dict[str, int]`, with `to_dict()` and `from_dict()` methods that raise `ValueError` on invalid regexes or negative bounds.

Add unit tests in `src/tests/test_assertion_schema.py`.
