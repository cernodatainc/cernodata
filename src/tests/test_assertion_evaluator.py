"""
src/tests/test_assertion_evaluator.py

Unit tests for the Level 3 assertion evaluator (TASK-102).
"""

from __future__ import annotations

import unittest

from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.dom.enums import DOMNodeType
from src.quality.assertion_evaluator import evaluate_assertions
from src.quality.violations import detect_quality_violations
from src.schemas.test_suite import DocumentAssertionSuite, HeaderAssertion, RegexAssertion

REQUIRED_KEYS = {
    "violation_id", "global_page_index", "node_id", "type",
    "rule_type", "severity", "description", "bounding_box",
}


def _node(node_id: str, node_type: str, text: str, page: int = 1) -> DOMNode:
    return DOMNode(
        node_id=node_id,
        type=node_type,
        global_page_index=page,
        temp_slice_index=page,
        bounding_box=BoundingBox(0.0, 0.0, 100.0, 20.0),
        content={"raw_text": text},
    )


def _dom(*nodes: DOMNode) -> DocumentDOM:
    return DocumentDOM(document_id="d", source_filename="d.pdf", total_pages=3, nodes=list(nodes))


def _evaluate(dom: DocumentDOM, **suite_kwargs):
    return evaluate_assertions(dom, DocumentAssertionSuite(**suite_kwargs))


class RequiredHeaderTests(unittest.TestCase):
    def test_matching_heading_passes(self) -> None:
        cases = {
            "literal": HeaderAssertion(text="Abstract"),
            "case_insensitive": HeaderAssertion(text="abstract"),
            "regex": HeaderAssertion(text=r"^Abs\w+", is_regex=True),
        }
        dom = _dom(_node("n1", "heading", "Abstract"))
        for label, rule in cases.items():
            with self.subTest(label):
                self.assertEqual(_evaluate(dom, required_headers=[rule]), [])

    def test_missing_header_is_document_level(self) -> None:
        dom = _dom(_node("n1", "heading", "ABSTRACT"))
        rule = HeaderAssertion(text="Abstract", case_sensitive=True)
        result = _evaluate(dom, required_headers=[rule])
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]["node_id"])
        self.assertEqual(result[0]["rule_type"], "required_header_missing")
        self.assertEqual(set(result[0]) & REQUIRED_KEYS, REQUIRED_KEYS)

    def test_misclassified_paragraph_is_reported_on_that_node(self) -> None:
        dom = _dom(_node("n1", "paragraph", "Abstract"))
        result = _evaluate(dom, required_headers=[HeaderAssertion(text="Abstract")])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["node_id"], "n1")
        self.assertIn("misclassified as a paragraph", result[0]["description"])

    def test_page_bounds_ignore_nodes_outside_range(self) -> None:
        rule = HeaderAssertion(text="References", min_page=2, max_page=3)
        for node_type in ("heading", "paragraph"):
            with self.subTest(node_type):
                result = _evaluate(_dom(_node("n1", node_type, "References", page=1)), required_headers=[rule])
                self.assertEqual(len(result), 1)
                self.assertIsNone(result[0]["node_id"])
                self.assertEqual(result[0]["global_page_index"], 2)


class RegexRuleTests(unittest.TestCase):
    def test_required_pattern_found(self) -> None:
        dom = _dom(_node("n1", "paragraph", "Invoice INV-1001 and INV-1002"))
        rule = RegexAssertion(pattern=r"INV-\d+", node_type=DOMNodeType.PARAGRAPH, min_matches=2)
        self.assertEqual(_evaluate(dom, regex_rules=[rule]), [])

    def test_required_pattern_below_min_matches(self) -> None:
        dom = _dom(_node("n1", "paragraph", "Invoice INV-1001"))
        rule = RegexAssertion(pattern=r"INV-\d+", node_type=DOMNodeType.PARAGRAPH, min_matches=2)
        result = _evaluate(dom, regex_rules=[rule])
        self.assertEqual([v["rule_type"] for v in result], ["required_pattern_missing"])

    def test_required_pattern_ignores_other_node_types(self) -> None:
        dom = _dom(_node("n1", "heading", "INV-1001"))
        rule = RegexAssertion(pattern=r"INV-\d+", node_type=DOMNodeType.PARAGRAPH)
        self.assertEqual(len(_evaluate(dom, regex_rules=[rule])), 1)

    def test_forbidden_pattern_flags_each_offending_node(self) -> None:
        dom = _dom(
            _node("n1", "paragraph", "Confidential - do not copy"),
            _node("n2", "paragraph", "Clean text"),
            _node("n3", "paragraph", "CONFIDENTIAL again"),
        )
        rule = RegexAssertion(pattern=r"(?i)confidential", node_type=DOMNodeType.PARAGRAPH, must_match=False)
        result = _evaluate(dom, regex_rules=[rule])
        self.assertEqual([v["node_id"] for v in result], ["n1", "n3"])
        self.assertTrue(all(v["rule_type"] == "forbidden_pattern_found" for v in result))

    def test_forbidden_pattern_absent_passes(self) -> None:
        dom = _dom(_node("n1", "paragraph", "Clean text"))
        rule = RegexAssertion(pattern=r"secret", node_type=DOMNodeType.PARAGRAPH, must_match=False)
        self.assertEqual(_evaluate(dom, regex_rules=[rule]), [])


class NodeCountTests(unittest.TestCase):
    def test_count_met(self) -> None:
        dom = _dom(_node("n1", "heading", "A"), _node("n2", "heading", "B"))
        self.assertEqual(_evaluate(dom, min_node_counts={"heading": 2}), [])

    def test_count_not_met(self) -> None:
        dom = _dom(_node("n1", "heading", "A"))
        result = _evaluate(dom, min_node_counts={"heading": 2, "table_grid": 1})
        self.assertEqual([v["rule_type"] for v in result], ["min_node_count", "min_node_count"])
        self.assertIn("expected at least 2", result[0]["description"])

    def test_enum_typed_nodes_are_counted(self) -> None:
        node = _node("n1", "heading", "A")
        node.type = DOMNodeType.HEADING
        self.assertEqual(_evaluate(_dom(node), min_node_counts={"heading": 1}), [])


class IntegrationTests(unittest.TestCase):
    def test_violation_ids_are_unique(self) -> None:
        dom = _dom(_node("n1", "paragraph", "text"))
        result = _evaluate(
            dom,
            required_headers=[HeaderAssertion(text="A"), HeaderAssertion(text="B")],
            min_node_counts={"heading": 1},
        )
        ids = [v["violation_id"] for v in result]
        self.assertEqual(len(ids), len(set(ids)))

    def test_detect_quality_violations_includes_suite_results(self) -> None:
        dom = _dom(_node("n1", "paragraph", "Body text"))
        suite = DocumentAssertionSuite(required_headers=[HeaderAssertion(text="Abstract")])
        with_suite = detect_quality_violations(dom, layers=["structure"], assertion_suite=suite)
        without_suite = detect_quality_violations(dom, layers=["structure"])
        self.assertEqual(len(with_suite) - len(without_suite), 1)
        self.assertEqual(with_suite[-1]["rule_type"], "required_header_missing")


if __name__ == "__main__":
    unittest.main()
