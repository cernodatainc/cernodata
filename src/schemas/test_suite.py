"""
src/schemas/test_suite.py

Declarative single-document assertion rules (TASK-101).

Users describe what a correctly parsed document must contain: headings, regex
matches, table shapes, and node counts. Suites round-trip through JSON via
`to_dict()` / `from_dict()`. Invalid regexes and negative bounds raise ValueError.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from src.dom.enums import DOMNodeType


def _require_non_negative(name: str, value: int) -> None:
    """Raises ValueError when value is negative."""
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value}")


def _require_valid_regex(pattern: str) -> None:
    """Raises ValueError when pattern is not a valid regular expression."""
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"invalid regex {pattern!r}: {exc}") from exc


@dataclass
class HeaderAssertion:
    """A heading that must appear, matched as literal text or as a regex.

    `case_sensitive` applies to both literal and regex matching.
    Page bounds are inclusive; None means unbounded.
    """

    text: str
    is_regex: bool = False
    case_sensitive: bool = False
    min_page: int | None = None
    max_page: int | None = None

    def __post_init__(self) -> None:
        if self.is_regex:
            _require_valid_regex(self.text)
        if self.min_page is not None:
            _require_non_negative("min_page", self.min_page)
        if self.max_page is not None:
            _require_non_negative("max_page", self.max_page)
        if self.min_page is not None and self.max_page is not None and self.min_page > self.max_page:
            raise ValueError(f"min_page ({self.min_page}) must be <= max_page ({self.max_page})")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HeaderAssertion:
        return cls(
            text=data["text"],
            is_regex=data.get("is_regex", False),
            case_sensitive=data.get("case_sensitive", False),
            min_page=data.get("min_page"),
            max_page=data.get("max_page"),
        )


@dataclass
class RegexAssertion:
    """A pattern that must (or must not) match within nodes of one type.

    `min_matches` applies only when `must_match` is True; with `must_match=False`
    any match is a failure and `min_matches` is ignored.
    """

    pattern: str
    node_type: DOMNodeType
    must_match: bool = True
    min_matches: int = 1

    def __post_init__(self) -> None:
        _require_valid_regex(self.pattern)
        _require_non_negative("min_matches", self.min_matches)
        self.node_type = DOMNodeType(self.node_type)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern,
            "node_type": self.node_type.value,
            "must_match": self.must_match,
            "min_matches": self.min_matches,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RegexAssertion:
        return cls(
            pattern=data["pattern"],
            node_type=data["node_type"],
            must_match=data.get("must_match", True),
            min_matches=data.get("min_matches", 1),
        )


@dataclass
class TableAssertion:
    """Minimum shape and expected content of a table."""

    min_columns: int = 0
    min_rows: int = 0
    expected_column_headers: list[str] = field(default_factory=list)
    numeric_column_indices: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_non_negative("min_columns", self.min_columns)
        _require_non_negative("min_rows", self.min_rows)
        for index in self.numeric_column_indices:
            _require_non_negative("numeric_column_indices item", index)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TableAssertion:
        return cls(
            min_columns=data.get("min_columns", 0),
            min_rows=data.get("min_rows", 0),
            expected_column_headers=list(data.get("expected_column_headers", [])),
            numeric_column_indices=list(data.get("numeric_column_indices", [])),
        )


@dataclass
class DocumentAssertionSuite:
    """All structural rules a single parsed document must satisfy."""

    required_headers: list[HeaderAssertion] = field(default_factory=list)
    regex_rules: list[RegexAssertion] = field(default_factory=list)
    table_rules: list[TableAssertion] = field(default_factory=list)
    min_node_counts: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        valid_types = {member.value for member in DOMNodeType}
        for node_type, count in self.min_node_counts.items():
            if node_type not in valid_types:
                raise ValueError(f"min_node_counts: unknown node type {node_type!r}; expected one of {sorted(valid_types)}")
            _require_non_negative(f"min_node_counts[{node_type!r}]", count)

    def to_dict(self) -> dict[str, Any]:
        return {
            "required_headers": [header.to_dict() for header in self.required_headers],
            "regex_rules": [rule.to_dict() for rule in self.regex_rules],
            "table_rules": [rule.to_dict() for rule in self.table_rules],
            "min_node_counts": dict(self.min_node_counts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentAssertionSuite:
        return cls(
            required_headers=[HeaderAssertion.from_dict(item) for item in data.get("required_headers", [])],
            regex_rules=[RegexAssertion.from_dict(item) for item in data.get("regex_rules", [])],
            table_rules=[TableAssertion.from_dict(item) for item in data.get("table_rules", [])],
            min_node_counts=dict(data.get("min_node_counts", {})),
        )
