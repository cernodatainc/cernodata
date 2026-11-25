"""
src/tests/test_retrieval_benchmark.py

Ground-truth retrieval benchmark (TASK-109) run through the BM25 sandbox and evaluator (TASK-105, TASK-106).

Each Markdown fixture is split into one DOM node per block, which stands in for a perfect parse.
Dropping blocks simulates parsers that lose footnotes or callouts.
"""

from __future__ import annotations

import json
import re
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.dom import DocumentDOM
from src.quality.retrieval_evaluator import evaluate_retrieval_suite
from src.schemas.test_suite import RetrievalTestSuite
from src.tests.conftest import make_test_node

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "retrieval_benchmark"
FAILURE_MODES = {
    "row_merge_in_table", "column_shift_in_table", "lost_footnote",
    "footnote_merged_into_body", "detached_section_header", "lost_callout", "control",
}

RAW: dict[str, Any] = json.loads((FIXTURES_DIR / "benchmark_questions.json").read_text(encoding="utf-8"))
SUITE = RetrievalTestSuite.from_dict(RAW)
DOC_PATHS = sorted(FIXTURES_DIR.glob("*.md"))
TEXTS = {path.name: path.read_text(encoding="utf-8") for path in DOC_PATHS}


def _block_type(block: str) -> str:
    if block.startswith("#"):
        return "heading"
    return "table_grid" if block.startswith("|") else "paragraph"


def _dom(path: Path, keep: Callable[[str], bool] = lambda block: True) -> DocumentDOM:
    blocks = [b.strip() for b in TEXTS[path.name].split("\n\n") if b.strip() and keep(b.strip())]
    nodes = []
    for index, block in enumerate(blocks):
        node = make_test_node(raw_text=block.lstrip("# "), node_id=f"{path.stem}_n{index}")
        node.type = _block_type(block)
        nodes.append(node)
    return DocumentDOM(document_id=path.stem, source_filename=path.name, total_pages=1, nodes=nodes)


def _failed_ids(documents: list[DocumentDOM]) -> set[str]:
    violations = evaluate_retrieval_suite(documents, SUITE)
    return {re.search(r"question '(\w+)'", v["description"]).group(1) for v in violations}  # type: ignore[union-attr]


def _ids_for(mode: str) -> set[str]:
    return {q["question_id"] for q in RAW["questions"] if q["failure_mode_tested"] == mode}


class BenchmarkFixtureTests(unittest.TestCase):
    """The fixture data itself is consistent, so a failing run points at the parser."""

    def test_question_metadata(self) -> None:
        questions = RAW["questions"]
        self.assertTrue(12 <= len(questions) - len(_ids_for("control")) <= 15)
        self.assertTrue({q["failure_mode_tested"] for q in questions} <= FAILURE_MODES)
        controls = [q["expected_source_docs"][0] for q in questions if q["failure_mode_tested"] == "control"]
        self.assertEqual(sorted(controls), sorted(TEXTS))

    def test_answers_and_distractors_are_unambiguous(self) -> None:
        for q in RAW["questions"]:
            source = q["expected_source_docs"][0]
            with self.subTest(question=q["question_id"]):
                for answer in q["expected_answer_substrings"]:
                    self.assertEqual([name for name, text in TEXTS.items() if answer in text], [source])
                for distractor in q.get("distractor_substrings", []):
                    self.assertIn(distractor, TEXTS[source])
                    self.assertNotIn(distractor, q["expected_answer_substrings"])


class BenchmarkRetrievalTests(unittest.TestCase):
    """A clean parse answers every question; losing structure fails the targeted questions."""

    def test_clean_parse_answers_every_question(self) -> None:
        self.assertEqual(_failed_ids([_dom(path) for path in DOC_PATHS]), set())

    def test_lost_footnotes_and_callouts_fail_their_questions(self) -> None:
        cases = {
            "lost_footnote": lambda block: not block.startswith("[^"),
            "lost_callout": lambda block: not block.startswith(">"),
        }
        for mode, keep in cases.items():
            with self.subTest(mode=mode):
                failed = _failed_ids([_dom(path, keep) for path in DOC_PATHS])
                self.assertEqual(failed, _ids_for(mode))


if __name__ == "__main__":
    unittest.main()
