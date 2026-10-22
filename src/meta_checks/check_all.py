"""
src/meta_checks/check_all.py

Consolidated meta checker executing all repository quality gates:
1. Strict Emoji Ban compliance
2. Type annotation completeness check across non-test sources
3. Ruff linting
4. Mypy static type checking
5. Pytest unit and integration test suite
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_emojis import check_files as check_emojis  # type: ignore[import-not-found]


def check_type_annotations(root_dir: Path) -> int:
    """Verifies that all functions and methods in non-test Python files have complete type annotations."""
    missing: List[Tuple[str, int, str]] = []

    class TypeInspector(ast.NodeVisitor):
        def __init__(self, filename: str) -> None:
            self.filename = filename

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._check_fn(node)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._check_fn(node)
            self.generic_visit(node)

        def _check_fn(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            if node.returns is None:
                missing.append((self.filename, node.lineno, f"{node.name}: missing return type annotation"))
            for arg in node.args.args:
                if arg.arg in ("self", "cls"):
                    continue
                if arg.annotation is None:
                    missing.append((self.filename, node.lineno, f"{node.name}({arg.arg}): missing argument type annotation"))
            for arg in node.args.kwonlyargs:
                if arg.annotation is None:
                    missing.append((self.filename, node.lineno, f"{node.name}({arg.arg}): missing kwonly argument type annotation"))
            if node.args.vararg and node.args.vararg.annotation is None:
                missing.append((self.filename, node.lineno, f"{node.name}(*{node.args.vararg.arg}): missing *args annotation"))
            if node.args.kwarg and node.args.kwarg.annotation is None:
                missing.append((self.filename, node.lineno, f"{node.name}(**{node.args.kwarg.arg}): missing **kwargs annotation"))

    src_dir = root_dir / "src"
    for py_file in src_dir.rglob("*.py"):
        if "tests" in py_file.parts:
            continue
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(py_file))
            TypeInspector(str(py_file)).visit(tree)
        except Exception as ex:
            missing.append((str(py_file), 0, f"Parse error: {ex}"))

    if missing:
        print(f"[FAIL] Missing type annotations found ({len(missing)} issues):")
        for filepath, lineno, desc in missing:
            print(f"  - {filepath}:{lineno} {desc}")
        return 1

    print("[PASS] Complete type annotations across all non-test sources.")
    return 0


def run_command(cmd: List[str], desc: str, cwd: Path) -> int:
    """Executes a command line tool and prints status."""
    print(f"\n--- Running: {desc} ({' '.join(cmd)}) ---")
    res = subprocess.run(cmd, cwd=cwd)
    if res.returncode != 0:
        print(f"[FAIL] {desc} returned non-zero exit code: {res.returncode}")
        return res.returncode
    print(f"[PASS] {desc} completed successfully.")
    return 0


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]

    print("====================================================================")
    print("cernodata Quality Verification Suite")
    print("====================================================================")

    # 1. Emoji ban
    print("\n--- Gate 1: Strict Emoji Ban Compliance ---")
    if check_emojis(repo_root) != 0:
        return 1

    # 2. Type annotation completeness
    print("\n--- Gate 2: Type Annotation Completeness ---")
    if check_type_annotations(repo_root) != 0:
        return 1

    # 3. Ruff linting
    if run_command(["ruff", "check", "src/"], "Ruff Linter", repo_root) != 0:
        return 1

    # 4. Mypy static type checking
    if run_command(["mypy"], "Mypy Type Checker", repo_root) != 0:
        return 1

    # 5. Pytest
    if run_command(["pytest", "-q"], "Pytest Test Suite", repo_root) != 0:
        return 1

    print("\n====================================================================")
    print("[SUCCESS] All repository quality gates passed.")
    print("====================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
