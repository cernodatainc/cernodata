"""
src/quality/table_validator.py
Scores how well table rows line up with the header row and checks a table
against a TableAssertion. Both work on `rows`, a list of rows of
cell strings whose first row is the header.
"""

from __future__ import annotations

import re
from typing import Sequence

from src.schemas.test_suite import TableAssertion

_NUMBER_RE = re.compile(
    r"^[-+(]?\s*[$€£]?\s*\d[\d\s.,]*\s*(?:[$€£%]|zł|PLN|EUR|USD)?\)?$",
    re.IGNORECASE,
)


def _normalize_rows(rows: Sequence[Sequence[object]]) -> list[list[str]]:
    """Normalizes raw cell sequences once into stripped string rows."""
    return [[str(cell if cell is not None else "").strip() for cell in row] for row in rows]


def compute_grid_consistency(rows: Sequence[Sequence[object]]) -> float:
    """Returns the fraction of rows with the header's column count, scaled down by the share of empty header cells."""
    norm_rows = _normalize_rows(rows)
    if not norm_rows or not norm_rows[0]:
        return 0.0
    header = norm_rows[0]
    matching = sum(1 for row in norm_rows if len(row) == len(header)) / len(norm_rows)
    empty_header_share = sum(1 for cell in header if not cell) / len(header)
    return matching * (1.0 - empty_header_share)


def check_table_assertion(rows: Sequence[Sequence[object]], rule: TableAssertion) -> list[str]:
    """Returns one message per failed condition of rule; empty when the table satisfies it."""
    norm_rows = _normalize_rows(rows)
    header = norm_rows[0] if norm_rows else []
    data_rows = norm_rows[1:]
    failures: list[str] = []

    if len(header) < rule.min_columns:
        failures.append(f"{len(header)} column(s), expected at least {rule.min_columns}")
    if len(data_rows) < rule.min_rows:
        failures.append(f"{len(data_rows)} data row(s), expected at least {rule.min_rows}")

    present = {cell.lower() for cell in header}
    missing = [name for name in rule.expected_column_headers if name.strip().lower() not in present]
    if missing:
        failures.append(f"missing column header(s): {missing}")

    for index in rule.numeric_column_indices:
        if norm_rows and index >= len(header) and not any(index < len(row) for row in data_rows):
            failures.append(f"column {index} out of range for table with {len(header)} column(s)")
            continue
        cells = [row[index] for row in data_rows if index < len(row) and row[index]]
        if any(not _NUMBER_RE.match(cell) for cell in cells):
            failures.append(f"column {index} has non-numeric value(s)")

    return failures
