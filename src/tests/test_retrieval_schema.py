"""
src/tests/test_retrieval_schema.py

Unit tests for the dataset retrieval test schema.
"""

from __future__ import annotations

import json
import unittest
from typing import Any

from src.schemas.test_suite import RetrievalQuestionCase, RetrievalTestSuite

VALID_SUITE: dict[str, Any] = {
    "suite_name": "pump_manual",
    "questions": [
        {
            "question_id": "q1",
            "question": "What is the maximum operating temperature of the pump?",
            "expected_answer_substrings": ["125 C", "257 F"],
            "expected_source_docs": ["pump.pdf"],
            "forbidden_substrings": ["TODO"],
            "top_k": 5,
        }
    ],
    "chunk_size_chars": 800,
    "chunk_overlap_chars": 100,
    "min_pass_rate": 0.9,
}


class TestRetrievalSchema(unittest.TestCase):
    def test_round_trip_through_json(self) -> None:
        suite = RetrievalTestSuite.from_dict(json.loads(json.dumps(VALID_SUITE)))
        self.assertEqual(suite.to_dict(), VALID_SUITE)

    def test_defaults(self) -> None:
        suite = RetrievalTestSuite.from_dict(
            {"suite_name": "s", "questions": [{"question_id": "q", "question": "?", "expected_answer_substrings": ["a"]}]}
        )
        case = suite.questions[0]
        self.assertEqual((case.top_k, case.expected_source_docs, case.forbidden_substrings), (3, None, []))
        self.assertEqual((suite.chunk_size_chars, suite.chunk_overlap_chars, suite.min_pass_rate), (1000, 150, 1.0))

    def test_invalid_input_raises_value_error(self) -> None:
        case = VALID_SUITE["questions"][0]
        invalid_cases = {
            "top_k below 1": lambda: RetrievalQuestionCase.from_dict({**case, "top_k": 0}),
            "min_pass_rate above 1": lambda: RetrievalTestSuite.from_dict({**VALID_SUITE, "min_pass_rate": 1.5}),
            "min_pass_rate below 0": lambda: RetrievalTestSuite.from_dict({**VALID_SUITE, "min_pass_rate": -0.1}),
            "overlap equals size": lambda: RetrievalTestSuite.from_dict(
                {**VALID_SUITE, "chunk_size_chars": 100, "chunk_overlap_chars": 100}
            ),
        }
        for label, build in invalid_cases.items():
            with self.subTest(label), self.assertRaises(ValueError):
                build()


if __name__ == "__main__":
    unittest.main()
