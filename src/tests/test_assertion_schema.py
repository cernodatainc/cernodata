"""
src/tests/test_assertion_schema.py

Unit tests for the single-document assertion schema (TASK-101).
"""

from __future__ import annotations

import json
import unittest

from src.dom.enums import DOMNodeType
from src.schemas.test_suite import (
    DocumentAssertionSuite,
    HeaderAssertion,
    RegexAssertion,
    TableAssertion,
)

VALID_SUITE = {
    "required_headers": [
        {"text": "Abstract"},
        {"text": "^Ref.*", "is_regex": True, "case_sensitive": True, "min_page": 2, "max_page": 9},
    ],
    "regex_rules": [{"pattern": r"INV-\d+", "node_type": "paragraph", "min_matches": 2}],
    "table_rules": [{"min_columns": 3, "min_rows": 2, "expected_column_headers": ["Item", "Qty", "Price"],
                     "numeric_column_indices": [1, 2]}],
    "min_node_counts": {"heading": 2, "table_grid": 1},
}


class TestAssertionSchema(unittest.TestCase):
    """Round-trip and validation tests for DocumentAssertionSuite and its rules."""

    def test_from_dict_parses_all_rule_types(self) -> None:
        suite = DocumentAssertionSuite.from_dict(VALID_SUITE)

        self.assertEqual(suite.required_headers[1], HeaderAssertion("^Ref.*", True, True, 2, 9))
        self.assertEqual(suite.regex_rules[0].node_type, DOMNodeType.PARAGRAPH)
        self.assertTrue(suite.regex_rules[0].must_match)
        self.assertEqual(suite.table_rules[0].numeric_column_indices, [1, 2])
        self.assertEqual(suite.min_node_counts, {"heading": 2, "table_grid": 1})

    def test_round_trip_through_json(self) -> None:
        suite = DocumentAssertionSuite.from_dict(VALID_SUITE)

        restored = DocumentAssertionSuite.from_dict(json.loads(json.dumps(suite.to_dict())))

        self.assertEqual(restored, suite)
        self.assertEqual(suite.to_dict()["regex_rules"][0]["node_type"], "paragraph")

    def test_empty_suite_is_valid(self) -> None:
        suite = DocumentAssertionSuite.from_dict({})

        self.assertEqual(suite, DocumentAssertionSuite())
        self.assertEqual(suite.to_dict()["table_rules"], [])

    def test_literal_header_text_is_not_compiled_as_regex(self) -> None:
        header = HeaderAssertion(text="Results (")

        self.assertFalse(header.is_regex)

    def test_invalid_input_raises_value_error(self) -> None:
        invalid_cases = {
            "header regex": {"required_headers": [{"text": "(", "is_regex": True}]},
            "negative min_page": {"required_headers": [{"text": "A", "min_page": -1}]},
            "min_page above max_page": {"required_headers": [{"text": "A", "min_page": 5, "max_page": 2}]},
            "rule regex": {"regex_rules": [{"pattern": "[a-", "node_type": "text"}]},
            "unknown node_type": {"regex_rules": [{"pattern": "x", "node_type": "list_item"}]},
            "negative min_matches": {"regex_rules": [{"pattern": "x", "node_type": "text", "min_matches": -1}]},
            "negative min_columns": {"table_rules": [{"min_columns": -1}]},
            "negative min_rows": {"table_rules": [{"min_rows": -2}]},
            "negative column index": {"table_rules": [{"numeric_column_indices": [0, -1]}]},
            "negative node count": {"min_node_counts": {"heading": -1}},
            "unknown node count key": {"min_node_counts": {"chapter": 1}},
        }
        for label, data in invalid_cases.items():
            with self.subTest(label), self.assertRaises(ValueError):
                DocumentAssertionSuite.from_dict(data)

    def test_direct_construction_is_validated(self) -> None:
        with self.assertRaises(ValueError):
            TableAssertion(min_columns=-1)
        with self.assertRaises(ValueError):
            RegexAssertion(pattern="(", node_type=DOMNodeType.TEXT)


if __name__ == "__main__":
    unittest.main()
