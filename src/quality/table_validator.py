"""
src/quality/table_validator.py
Scores how well table rows line up with the header row and checks a table
against a TableAssertion. Both work on `rows`, a list of rows of
cell strings whose first row is the header.
"""

from __future__ import annotations

import re

from src.schemas.test_suite import TableAssertion

_NUMBER_RE = re.compile(
    r"^[-+(]?\s*[$€£]?\s*\d[\d\s.,]*\s*(?:[$€£%]|zł|PLN|EUR|USD)?\)?$",
    re.IGNORECASE,
)


def compute_grid_consistency(rows: list[list[str]]) -> float:
    """Returns the fraction of rows with the header's column count, scaled down by the share of empty header cells."""
    if not rows or not rows[0]:
        return 0.0
    header = rows[0]
    matching = sum(1 for row in rows if len(row) == len(header)) / len(rows)
    empty_header_share = sum(1 for cell in header if not cell.strip()) / len(header)
    return matching * (1.0 - empty_header_share)


def check_table_assertion(rows: list[list[str]], rule: TableAssertion) -> list[str]:
    """Returns one message per failed condition of rule; empty when the table satisfies it."""
    header = rows[0] if rows else []
    data_rows = rows[1:]
    failures: list[str] = []

    if len(header) < rule.min_columns:
        failures.append(f"{len(header)} column(s), expected at least {rule.min_columns}")
    if len(data_rows) < rule.min_rows:
        failures.append(f"{len(data_rows)} data row(s), expected at least {rule.min_rows}")

    present = {cell.strip().lower() for cell in header}
    missing = [name for name in rule.expected_column_headers if name.strip().lower() not in present]
    if missing:
        failures.append(f"missing column header(s): {missing}")

    for index in rule.numeric_column_indices:
        cells = [row[index].strip() for row in data_rows if index < len(row) and row[index].strip()]
        if any(not _NUMBER_RE.match(cell) for cell in cells):
            failures.append(f"column {index} has non-numeric value(s)")

    return failures
