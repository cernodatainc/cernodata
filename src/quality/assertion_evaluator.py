"""
src/quality/assertion_evaluator.py

Level 3 structural spot-checker (TASK-102).

Checks a DocumentDOM against a DocumentAssertionSuite (TASK-101) and returns
violation dicts compatible with src/quality/violations.py. Failures with no
node to point at use node_id None and a zero bounding box.
"""

from __future__ import annotations

import re
from typing import Any

from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.dom.enums import DOMNodeType
from src.quality.handlers import make_node_violation
from src.quality.layers import VerificationLayer
from src.schemas.test_suite import DocumentAssertionSuite, HeaderAssertion

_LAYER = VerificationLayer.STRUCTURE.value


def _type_value(node: DOMNode) -> str:
    return node.type.value if isinstance(node.type, DOMNodeType) else str(node.type)


def _text(node: DOMNode) -> str:
    return str(node.content.get("raw_text") or "").strip()


def _document_violation(counter: int, page: int, rule_type: str, severity: str, description: str) -> dict[str, Any]:
    """Builds a violation record that is not tied to a single node."""
    return {
        "violation_id": f"viol_p{page}_v{counter}",
        "global_page_index": page,
        "node_id": None,
        "type": _LAYER,
        "rule_type": rule_type,
        "severity": severity,
        "suppressed": False,
        "description": description,
        "bounding_box": BoundingBox(0.0, 0.0, 0.0, 0.0).to_dict(),
    }


def _header_matches(rule: HeaderAssertion, text: str) -> bool:
    flags = 0 if rule.case_sensitive else re.IGNORECASE
    pattern = rule.text if rule.is_regex else re.escape(rule.text)
    return re.search(pattern, text, flags) is not None


def evaluate_assertions(
    dom: DocumentDOM, suite: DocumentAssertionSuite, counter: int = 1
) -> list[dict[str, Any]]:
    """Returns one violation per failed rule in suite (forbidden patterns: one per offending node)."""
    violations: list[dict[str, Any]] = []

    def next_id() -> int:
        return counter + len(violations)

    for header in suite.required_headers:
        in_range = [
            n for n in dom.nodes
            if (header.min_page is None or n.global_page_index >= header.min_page)
            and (header.max_page is None or n.global_page_index <= header.max_page)
        ]
        if any(_type_value(n) == "heading" and _header_matches(header, _text(n)) for n in in_range):
            continue
        paragraph = next(
            (n for n in in_range if _type_value(n) == "paragraph" and _header_matches(header, _text(n))), None
        )
        if paragraph is not None:
            violations.append(make_node_violation(
                node=paragraph, counter=next_id(), v_type=_LAYER, rule_type="required_header_missing",
                description=(
                    f"Required header {header.text!r} not found among headings; "
                    "heading text was found in body text but misclassified as a paragraph"
                ),
            ))
        else:
            violations.append(_document_violation(
                next_id(), header.min_page or 1, "required_header_missing", "ERROR",
                f"Required header {header.text!r} not found",
            ))

    for rule in suite.regex_rules:
        pattern = re.compile(rule.pattern)
        nodes = [n for n in dom.nodes if _type_value(n) == rule.node_type.value]
        if rule.must_match:
            total = sum(len(pattern.findall(_text(n))) for n in nodes)
            if total < rule.min_matches:
                violations.append(_document_violation(
                    next_id(), 1, "required_pattern_missing", "ERROR",
                    f"Pattern {rule.pattern!r} matched {total} time(s) in {rule.node_type.value} nodes; "
                    f"expected at least {rule.min_matches}",
                ))
            continue
        for node in nodes:
            if pattern.search(_text(node)):
                violations.append(make_node_violation(
                    node=node, counter=next_id(), v_type=_LAYER, rule_type="forbidden_pattern_found",
                    description=f"Forbidden pattern {rule.pattern!r} found in {rule.node_type.value} node",
                ))

    for node_type, minimum in suite.min_node_counts.items():
        actual = sum(1 for n in dom.nodes if _type_value(n) == node_type)
        if actual < minimum:
            violations.append(_document_violation(
                next_id(), 1, "min_node_count", "ERROR",
                f"Found {actual} {node_type} node(s); expected at least {minimum}",
            ))

    return violations
