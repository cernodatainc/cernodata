"""
src/tests/test_table_validator.py

Unit tests for the table grid validator
"""

from __future__ import annotations

import unittest

from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.parsers.table_parser import parse_markdown_table
from src.quality.table_validator import check_table_assertion, compute_grid_consistency
from src.quality.violations import detect_quality_violations
from src.schemas.test_suite import DocumentAssertionSuite, TableAssertion

GOOD_ROWS = [["Item", "Qty", "Price"], ["Pen", "2", "3,50 PLN"], ["Ink", "1", "$12.00"]]


def _table_dom(rows: list[list[str]]) -> DocumentDOM:
    node = DOMNode(
        node_id="t1",
        type="table_grid",
        global_page_index=1,
        temp_slice_index=1,
        bounding_box=BoundingBox(0.0, 0.0, 100.0, 50.0),
        content={"raw_text": "table", "rows": rows, "cell_alignment_score": 1.0},
    )
    return DocumentDOM(document_id="d", source_filename="d.pdf", total_pages=1, nodes=[node])


class GridConsistencyTests(unittest.TestCase):
    def test_aligned_table_scores_one(self) -> None:
        self.assertEqual(compute_grid_consistency(GOOD_ROWS), 1.0)

    def test_ragged_rows_lower_score(self) -> None:
        rows = [["A", "B", "C"], ["1", "2", "3"], ["4", "5"], ["6"]]
        self.assertAlmostEqual(compute_grid_consistency(rows), 0.5)

    def test_empty_header_cells_lower_score(self) -> None:
        rows = [["A", "", "C", ""], ["1", "2", "3", "4"]]
        self.assertAlmostEqual(compute_grid_consistency(rows), 0.5)

    def test_empty_table_scores_zero(self) -> None:
        self.assertEqual(compute_grid_consistency([]), 0.0)

    def test_parser_score_uses_validator(self) -> None:
        ragged = parse_markdown_table("| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 |")
        self.assertLess(ragged.cell_alignment_score, 1.0)


class TableAssertionTests(unittest.TestCase):
    def test_satisfied_rule_has_no_failures(self) -> None:
        rule = TableAssertion(
            min_columns=3, min_rows=2, expected_column_headers=["item", "PRICE"], numeric_column_indices=[1, 2]
        )
        self.assertEqual(check_table_assertion(GOOD_ROWS, rule), [])

    def test_each_condition_is_reported(self) -> None:
        cases = {
            "min_columns": TableAssertion(min_columns=4),
            "min_rows": TableAssertion(min_rows=3),
            "expected_column_headers": TableAssertion(expected_column_headers=["Total"]),
            "numeric_column_indices": TableAssertion(numeric_column_indices=[0]),
        }
        for label, rule in cases.items():
            with self.subTest(label):
                self.assertEqual(len(check_table_assertion(GOOD_ROWS, rule)), 1)

    def test_empty_table_fails_min_columns(self) -> None:
        self.assertEqual(len(check_table_assertion([], TableAssertion(min_columns=1))), 1)


class ViolationWiringTests(unittest.TestCase):
    def test_failed_assertion_emits_table_violation(self) -> None:
        suite = DocumentAssertionSuite(table_rules=[TableAssertion(min_columns=5)])
        result = detect_quality_violations(_table_dom(GOOD_ROWS), layers=["tables"], assertion_suite=suite)
        self.assertEqual([v["rule_type"] for v in result], ["table_assertion_failed"])
        self.assertEqual(result[0]["node_id"], "t1")

    def test_satisfied_assertion_emits_nothing(self) -> None:
        suite = DocumentAssertionSuite(table_rules=[TableAssertion(min_columns=3)])
        self.assertEqual(detect_quality_violations(_table_dom(GOOD_ROWS), layers=["tables"], assertion_suite=suite), [])


if __name__ == "__main__":
    unittest.main()
