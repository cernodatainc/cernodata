"""
src/tests/test_retrieval_evaluator.py

Unit tests for the Level 5 retrieval test evaluator (TASK-106).
"""

from __future__ import annotations

import unittest
from typing import Any

from src.dom import DOMNode, DocumentDOM
from src.quality.retrieval_evaluator import RULE_TYPE, evaluate_retrieval_suite
from src.quality.violations import detect_quality_violations
from src.schemas.test_suite import RetrievalQuestionCase, RetrievalTestSuite
from src.tests.conftest import make_test_node

REQUIRED_KEYS = {
    "violation_id", "global_page_index", "node_id", "type",
    "rule_type", "severity", "description", "bounding_box",
}


def _node(node_id: str, text: str, page: int = 1, confidence: float | None = None) -> DOMNode:
    node = make_test_node(raw_text=text, node_id=node_id, page=page)
    node.ocr_confidence = confidence
    return node


def _dom(doc_id: str, *nodes: DOMNode) -> DocumentDOM:
    return DocumentDOM(document_id=doc_id, source_filename=f"{doc_id}.pdf", total_pages=3, nodes=list(nodes))


def _case(**overrides: Any) -> RetrievalQuestionCase:
    fields: dict[str, Any] = {
        "question_id": "q1",
        "question": "What is the maximum pump temperature?",
        "expected_answer_substrings": ["125 C"],
        "top_k": 1,
    }
    fields.update(overrides)
    return RetrievalQuestionCase(**fields)


def _suite(*cases: RetrievalQuestionCase) -> RetrievalTestSuite:
    return RetrievalTestSuite(suite_name="s", questions=list(cases), chunk_size_chars=200, chunk_overlap_chars=0)


MANUAL = _dom("manual", _node("n1", "The maximum pump temperature is 125 C."))
BROCHURE = _dom("brochure", _node("b1", "Our pump range is CONFIDENTIAL draft material."))


class QuestionCheckTests(unittest.TestCase):
    def test_answered_question_passes(self) -> None:
        cases = {
            "exact": _case(),
            "case and whitespace insensitive": _case(expected_answer_substrings=["125   c"]),
            "source by document_id": _case(expected_source_docs=["manual"]),
            "source by filename": _case(expected_source_docs=["manual.pdf"]),
            "forbidden absent": _case(forbidden_substrings=["confidential"]),
        }
        for label, case in cases.items():
            with self.subTest(label):
                self.assertEqual(evaluate_retrieval_suite([MANUAL, BROCHURE], _suite(case)), [])

    def test_missing_answer_is_document_level_violation(self) -> None:
        result = evaluate_retrieval_suite([MANUAL], _suite(_case(expected_answer_substrings=["125 C", "257 F"])))
        self.assertEqual(len(result), 1)
        violation = result[0]
        self.assertEqual(set(violation) & REQUIRED_KEYS, REQUIRED_KEYS)
        self.assertEqual((violation["rule_type"], violation["node_id"]), (RULE_TYPE, None))
        self.assertIn("'q1'", violation["description"])
        self.assertIn("'257 F'", violation["description"])
        self.assertNotIn("'125 C'", violation["description"])

    def test_wrong_source_document_fails(self) -> None:
        result = evaluate_retrieval_suite([MANUAL, BROCHURE], _suite(_case(expected_source_docs=["brochure.pdf"])))
        self.assertEqual(len(result), 1)
        self.assertIn("expected source document(s) ['brochure.pdf']", result[0]["description"])

    def test_forbidden_text_in_top_k_fails(self) -> None:
        case = _case(question="pump range", expected_answer_substrings=[], forbidden_substrings=["confidential"])
        result = evaluate_retrieval_suite([MANUAL, BROCHURE], _suite(case))
        self.assertEqual(len(result), 1)
        self.assertIn("forbidden text ['confidential']", result[0]["description"])

    def test_no_documents_fails_every_question(self) -> None:
        result = evaluate_retrieval_suite([], _suite(_case(), _case(question_id="q2")))
        self.assertEqual([v["rule_type"] for v in result], [RULE_TYPE, RULE_TYPE])

    def test_violation_ids_continue_from_counter_and_are_unique(self) -> None:
        cases = [_case(question_id=f"q{i}", expected_answer_substrings=["absent"]) for i in range(3)]
        result = evaluate_retrieval_suite([MANUAL], _suite(*cases), counter=10)
        self.assertEqual([v["violation_id"] for v in result], ["viol_p1_v10", "viol_p1_v11", "viol_p1_v12"])


class LowConfidenceAttributionTests(unittest.TestCase):
    def _evaluate(self, answer_node: DOMNode) -> list[dict[str, Any]]:
        corpus = [
            _dom("manual", _node("n1", "Pump temperature limits are listed in the appendix.")),
            _dom("appendix", answer_node),
        ]
        return evaluate_retrieval_suite(corpus, _suite(_case(question="pump temperature")))

    def test_missing_answer_in_low_confidence_node_points_at_it(self) -> None:
        low_confidence = {
            "ocr_confidence below threshold": _node("a1", "Value: 125 C", page=2, confidence=0.3),
            "flagged incorrect text": _node("a1", "Value: 125 C", page=2),
        }
        low_confidence["flagged incorrect text"].is_incorrect_text = True
        for label, node in low_confidence.items():
            with self.subTest(label):
                result = self._evaluate(node)
                self.assertEqual(len(result), 1)
                self.assertEqual((result[0]["node_id"], result[0]["global_page_index"]), ("a1", 2))
                self.assertEqual(result[0]["detected_snippet"], "125 C")
                self.assertEqual(result[0]["violation_id"], "viol_p2_v1")

    def test_missing_answer_in_confident_node_stays_document_level(self) -> None:
        for confidence in (None, 0.95):
            with self.subTest(confidence=confidence):
                result = self._evaluate(_node("a1", "Value: 125 C", page=2, confidence=confidence))
                self.assertEqual(len(result), 1)
                self.assertIsNone(result[0]["node_id"])


class DetectQualityViolationsHookTests(unittest.TestCase):
    def test_retrieval_suite_adds_violations(self) -> None:
        dom = _dom("d", _node("n1", "Body text about pumps."))
        suite = _suite(_case(question="pumps", expected_answer_substrings=["125 C"]))
        without_suite = detect_quality_violations(dom, layers=["structure"])
        with_suite = detect_quality_violations(dom, layers=["structure"], retrieval_suite=suite)
        self.assertEqual(len(with_suite) - len(without_suite), 1)
        self.assertEqual(with_suite[-1]["rule_type"], RULE_TYPE)
        self.assertEqual(len({v["violation_id"] for v in with_suite}), len(with_suite))


if __name__ == "__main__":
    unittest.main()
