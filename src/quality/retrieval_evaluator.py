"""
src/quality/retrieval_evaluator.py

Level 5 retrieval test evaluator (TASK-106).

Indexes parsed DocumentDOMs into LexicalRetrievalSandbox (TASK-105) and runs every
RetrievalQuestionCase of a RetrievalTestSuite (TASK-104) against its top-k chunks.
Each failed question yields one `rag_retrieval_recall_miss` violation compatible with
src/quality/violations.py. When a missing answer exists inside a low-confidence node,
the violation points at that node so the fallback loop knows which page to re-parse.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.quality.handlers import make_node_violation
from src.quality.retrieval_sandbox import IndexedChunk, LexicalRetrievalSandbox
from src.schemas.test_suite import RetrievalQuestionCase, RetrievalTestSuite

RULE_TYPE = "rag_retrieval_recall_miss"
VIOLATION_TYPE = "retrieval"
# Mirrors DEFAULT_TARGET_CONFIDENCE_THRESHOLD in src/pipeline/decision_tree.py.
LOW_CONFIDENCE_THRESHOLD = 0.82

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """Case- and whitespace-insensitive form used for all substring checks."""
    return _WHITESPACE_RE.sub(" ", text).strip().lower()


def _is_low_confidence(node: DOMNode, threshold: float) -> bool:
    return bool(node.is_incorrect_text) or (node.ocr_confidence is not None and node.ocr_confidence < threshold)


def _check_question(
    case: RetrievalQuestionCase,
    results: list[tuple[IndexedChunk, float]],
    doc_names: dict[str, set[str]],
) -> tuple[list[str], list[str]]:
    """Returns (missing answer substrings, failure messages) for one question's top-k results."""
    retrieved = [_normalize(chunk.text) for chunk, _ in results]

    def found(substring: str) -> bool:
        needle = _normalize(substring)
        return any(needle in text for text in retrieved)

    missing = [s for s in case.expected_answer_substrings if not found(s)]
    failures = [f"missing expected answer text {missing}"] if missing else []

    if case.expected_source_docs is not None:
        retrieved_docs: set[str] = set()
        for chunk, _ in results:
            retrieved_docs |= doc_names.get(chunk.doc_id, {chunk.doc_id})
        absent = [doc for doc in case.expected_source_docs if doc not in retrieved_docs]
        if absent:
            failures.append(f"expected source document(s) {absent} not in top-{case.top_k} results")

    forbidden = [s for s in case.forbidden_substrings if found(s)]
    if forbidden:
        failures.append(f"forbidden text {forbidden} found in top-{case.top_k} results")
    return missing, failures


def _find_low_confidence_node(
    documents: Sequence[DocumentDOM], missing: list[str], threshold: float
) -> tuple[DOMNode, str] | None:
    """Returns the first low-confidence node containing a missing answer substring, with that substring."""
    needles = [(substring, _normalize(substring)) for substring in missing]
    for dom in documents:
        for node in dom.nodes:
            if not _is_low_confidence(node, threshold):
                continue
            text = _normalize(node.text)
            for substring, needle in needles:
                if needle in text:
                    return node, substring
    return None


def _document_violation(counter: int, description: str) -> dict[str, Any]:
    """Builds a violation record that is not tied to a single node."""
    return {
        "violation_id": f"viol_p1_v{counter}",
        "global_page_index": 1,
        "node_id": None,
        "type": VIOLATION_TYPE,
        "rule_type": RULE_TYPE,
        "severity": "ERROR",
        "suppressed": False,
        "description": description,
        "bounding_box": BoundingBox(0.0, 0.0, 0.0, 0.0).to_dict(),
    }


def evaluate_retrieval_suite(
    documents: Sequence[DocumentDOM],
    suite: RetrievalTestSuite,
    counter: int = 1,
    low_confidence_threshold: float = LOW_CONFIDENCE_THRESHOLD,
) -> list[dict[str, Any]]:
    """Returns one violation per question in suite that its top-k retrieved chunks fail to answer."""
    sandbox = LexicalRetrievalSandbox()
    sandbox.index_documents(
        list(documents), chunk_size_chars=suite.chunk_size_chars, chunk_overlap_chars=suite.chunk_overlap_chars
    )
    doc_names = {dom.document_id: {dom.document_id, dom.source_filename} for dom in documents}
    violations: list[dict[str, Any]] = []

    for case in suite.questions:
        results = sandbox.query(case.question, top_k=case.top_k)
        missing, failures = _check_question(case, results, doc_names)
        if not failures:
            continue
        description = f"Retrieval question {case.question_id!r} ({case.question!r}) failed: " + "; ".join(failures)
        match = _find_low_confidence_node(documents, missing, low_confidence_threshold) if missing else None
        if match is None:
            violations.append(_document_violation(counter + len(violations), description))
            continue
        node, substring = match
        violations.append(make_node_violation(
            node=node,
            counter=counter + len(violations),
            v_type=VIOLATION_TYPE,
            rule_type=RULE_TYPE,
            severity="ERROR",
            detected_snippet=substring,
            description=f"{description}; missing text {substring!r} is in low-confidence node {node.node_id!r}",
        ))

    return violations
