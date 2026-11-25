"""
src/quality/test_suite_check.py

Evaluates Web Hub output expectations (TASK-107) against one parsed document.

Combines a domain template (TASK-108) with user-entered headers, a minimum table width, and
question/answer pairs, and reports pass/fail for every rule, so the UI can show both green and red
badges. Rules reuse the TASK-102/103/106 evaluators one at a time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.dom import DocumentDOM
from src.quality.assertion_evaluator import evaluate_assertions
from src.quality.retrieval_evaluator import evaluate_retrieval_suite
from src.quality.table_validator import check_table_assertion
from src.schemas.test_suite import (
    DocumentAssertionSuite,
    HeaderAssertion,
    RegexAssertion,
    RetrievalQuestionCase,
    RetrievalTestSuite,
    TableAssertion,
)

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "schemas" / "examples" / "assertion_templates"


def list_templates() -> list[str]:
    """Returns the names of the available assertion templates."""
    return sorted(path.stem for path in TEMPLATES_DIR.glob("*.json"))


def _load_template(name: str | None) -> dict[str, Any]:
    if not name:
        return {}
    if name not in list_templates():
        raise ValueError(f"unknown template {name!r}")
    return json.loads((TEMPLATES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _descriptions(violations: list[dict[str, Any]]) -> list[str]:
    return [str(v["description"]) for v in violations]


def run_test_suite_check(dom: DocumentDOM, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Returns one {id, type, label, passed, detail} record per rule and question in payload."""
    template = _load_template(payload.get("template"))
    headers = template.get("required_headers", []) + [
        {"text": text.strip()} for text in payload.get("required_headers", []) if text.strip()
    ]
    tables = template.get("table_rules", []) + (
        [{"min_columns": int(payload["min_table_columns"])}] if payload.get("min_table_columns") else []
    )
    table_rows = [node.table_rows or [] for node in dom.nodes if node.table_rows is not None]
    results: list[dict[str, Any]] = []

    def add(kind: str, label: str, failures: list[str]) -> None:
        results.append({
            "id": f"{kind}_{len(results) + 1}",
            "type": kind,
            "label": label,
            "passed": not failures,
            "detail": "; ".join(failures),
        })

    for raw in headers:
        header = HeaderAssertion.from_dict(raw)
        suite = DocumentAssertionSuite(required_headers=[header])
        add("header", raw.get("description") or f"Heading '{header.text}'", _descriptions(evaluate_assertions(dom, suite)))
    for raw in template.get("regex_rules", []):
        rule = RegexAssertion.from_dict(raw)
        suite = DocumentAssertionSuite(regex_rules=[rule])
        add("pattern", raw.get("description") or rule.pattern, _descriptions(evaluate_assertions(dom, suite)))
    for node_type, minimum in template.get("min_node_counts", {}).items():
        suite = DocumentAssertionSuite(min_node_counts={node_type: minimum})
        add("node_count", f"At least {minimum} {node_type} node(s)", _descriptions(evaluate_assertions(dom, suite)))
    for raw in tables:
        table_rule = TableAssertion.from_dict(raw)
        failures = [
            f"table {index}: {message}"
            for index, rows in enumerate(table_rows, start=1)
            for message in check_table_assertion(rows, table_rule)
        ]
        add("table", raw.get("description") or f"Every table has at least {table_rule.min_columns} columns", failures)
    for index, item in enumerate(payload.get("questions", []), start=1):
        case = RetrievalQuestionCase(
            question_id=f"q{index}", question=item["question"], expected_answer_substrings=[item["expected_answer"]]
        )
        suite_q = RetrievalTestSuite(suite_name="web_hub", questions=[case])
        add("question", f"{item['question']} -> {item['expected_answer']}",
            _descriptions(evaluate_retrieval_suite([dom], suite_q)))
    return results
