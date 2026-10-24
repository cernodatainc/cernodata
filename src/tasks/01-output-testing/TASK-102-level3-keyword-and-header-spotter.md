# TASK-102: Structural and header spot-checker

Depends on: TASK-101

Once `DocumentAssertionSuite` (`TASK-101`) exists, we need an evaluator that checks a parsed `DocumentDOM` (`src/dom/document.py`) against those rules and returns violation records compatible with `src/quality/violations.py`.

Create `src/quality/assertion_evaluator.py` and wire it into `_check_structural_assertion_violations` in `src/quality/violations.py`:

- Check `required_headers` against `DOMNode` items where `node.type == "heading"`. If a required header is missing from headings, check whether the text appears inside a regular `paragraph` node on the expected pages; if so, note in the violation description that the heading text was found in body text but misclassified as a paragraph.
- Check `regex_rules` (`must_match=True` for required patterns like invoice numbers, `must_match=False` for forbidden boilerplate).
- Check `min_node_counts` per node type.
- Return violation dicts matching the schema in `src/quality/violations.py` (`violation_id`, `global_page_index`, `node_id`, `type`, `rule_type`, `severity`, `description`, `bounding_box`).

Add unit tests in `src/tests/test_assertion_evaluator.py`.
