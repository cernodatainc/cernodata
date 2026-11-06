"""
src/tests/test_check_function_parameters.py

Unit tests for function parameter layout enforcement:
- Either all function parameters are on the same line (120 character limit)
- Or all on different lines
"""

from __future__ import annotations

import unittest
from pathlib import Path

from src.meta_checks.check_function_parameters import (
    check_files,
    inspect_file,
    inspect_source,
)


class TestFunctionParameterLayout(unittest.TestCase):
    """Validates parameter layout checking for both single-line and multiline forms."""

    def test_same_line_under_limit_passes(self) -> None:
        """Parameters all on the same line under 120 characters are compliant."""
        src = "def process(a: int, b: str, c: float = 1.0) -> bool:\n    return True\n"
        issues = inspect_source(src, filename="test.py")
        self.assertEqual(issues, [])

    def test_same_line_over_limit_fails(self) -> None:
        """Parameters all on the same line exceeding 120 characters are flagged."""
        src = (
            "def calculate_composite_score_with_multiple_parameters("
            "primary_metric: float, secondary_metric: float, normalization_factor: float = 1.0"
            ") -> float:\n    return 0.0\n"
        )
        self.assertGreater(len(src.splitlines()[0]), 120)
        issues = inspect_source(src, filename="test.py")
        self.assertEqual(len(issues), 1)
        self.assertIn("exceeds 120 characters", issues[0])

    def test_all_different_lines_passes(self) -> None:
        """Parameters each placed on a separate distinct line are compliant."""
        src = (
            "def process(\n"
            "    primary_metric: float,\n"
            "    secondary_metric: float,\n"
            "    normalization_factor: float = 1.0,\n"
            ") -> float:\n"
            "    return 0.0\n"
        )
        issues = inspect_source(src, filename="test.py")
        self.assertEqual(issues, [])

    def test_mixed_lines_fails(self) -> None:
        """Parameters mixed across lines (some sharing a line, some on different lines) are flagged."""
        src = (
            "def process(\n"
            "    a: int, b: int,\n"
            "    c: int,\n"
            ") -> None:\n"
            "    pass\n"
        )
        issues = inspect_source(src, filename="test.py")
        self.assertEqual(len(issues), 1)
        self.assertIn("multiple parameters sharing line", issues[0])

    def test_async_function_support(self) -> None:
        """Async functions are also subject to parameter line layout enforcement."""
        bad_src = (
            "async def handle_request(\n"
            "    req_id: str, payload: dict,\n"
            "    timeout: float = 30.0,\n"
            ") -> None:\n"
            "    pass\n"
        )
        issues = inspect_source(bad_src, filename="async_test.py")
        self.assertEqual(len(issues), 1)
        self.assertIn("multiple parameters sharing line", issues[0])

        good_src = (
            "async def handle_request(\n"
            "    req_id: str,\n"
            "    payload: dict,\n"
            "    timeout: float = 30.0,\n"
            ") -> None:\n"
            "    pass\n"
        )
        clean_issues = inspect_source(good_src, filename="async_test.py")
        self.assertEqual(clean_issues, [])

    def test_multiline_parameter_overlap_fails(self) -> None:
        """A parameter starting on the line where a previous multiline parameter ends is flagged."""
        src = (
            "def transform(\n"
            "    data: dict[\n"
            "        str, int], extra: int = 1,\n"
            ") -> None:\n"
            "    pass\n"
        )
        issues = inspect_source(src, filename="test.py")
        self.assertEqual(len(issues), 1)
        self.assertIn("overlaps with parameter", issues[0])

    def test_zero_parameters_passes(self) -> None:
        """Functions with no parameters are always compliant."""
        src = "def no_args() -> None:\n    pass\n"
        issues = inspect_source(src, filename="test.py")
        self.assertEqual(issues, [])

    def test_single_parameter_multiline_passes(self) -> None:
        """Single parameter formatted on its own line passes."""
        src = (
            "def single_arg(\n"
            "    data: dict[str, list[int]],\n"
            ") -> None:\n"
            "    pass\n"
        )
        issues = inspect_source(src, filename="test.py")
        self.assertEqual(issues, [])

    def test_vararg_and_kwarg_handled(self) -> None:
        """*args and **kwargs are verified as parameters in layout."""
        bad_src = (
            "def variadic(\n"
            "    first: int,\n"
            "    *args: int, **kwargs: str,\n"
            ") -> None:\n"
            "    pass\n"
        )
        issues = inspect_source(bad_src, filename="variadic.py")
        self.assertEqual(len(issues), 1)

        good_src = (
            "def variadic(\n"
            "    first: int,\n"
            "    *args: int,\n"
            "    **kwargs: str,\n"
            ") -> None:\n"
            "    pass\n"
        )
        self.assertEqual(inspect_source(good_src, filename="variadic.py"), [])

    def test_repository_files_compliant(self) -> None:
        """Verifies that all Python files in src/ comply with parameter layout."""
        repo_root = Path(__file__).resolve().parents[2]
        res = check_files(repo_root / "src")
        self.assertEqual(res, 0)

    def test_inspect_file_on_disk(self) -> None:
        """Verifies inspect_file correctly parses a file on disk."""
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write("def f(a: int, b: int) -> None:\n    pass\n")
            f_path = Path(f.name)
        try:
            issues = inspect_file(f_path)
            self.assertEqual(issues, [])
        finally:
            f_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
