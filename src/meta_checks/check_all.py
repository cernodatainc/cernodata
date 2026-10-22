"""
src/meta_checks/check_all.py

Consolidated meta checker executing all repository quality gates:
1. Strict Emoji Ban compliance
2. File hygiene & length thresholds (< 500 lines) and inline CSS/JS rules
3. Type annotation completeness check across non-test sources
4. AST code hygiene (UTF-8 BOM, unused imports, bare excepts, mutable defaults)
5. Architectural silo invariant validation (Planner strictly decoupled)
6. Ruff linting
7. Mypy static type checking
8. Pytest unit and integration test suite
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

from src.meta_checks.check_ast import run_checks as check_ast
from src.meta_checks.check_emojis import check_files as check_emojis
from src.meta_checks.file_hygiene import run_meta_checks
from src.meta_checks.visualize_dependencies import build_dependency_graph, verify_planner_silo


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


def check_hygiene(root_dir: Path) -> int:
    """Verifies file length limits (< 500 lines) and flags unmuted inline CSS/JS."""
    res = run_meta_checks(str(root_dir))
    if not res["is_passed"]:
        print("[FAIL] File hygiene checks failed:")
        for lv in res["length_violations"]:
            print(f"  - [RED FLAG] {lv['message']}")
        for iv in res["inline_violations"]:
            print(f"  - [INLINE] {iv['message']}")
        return 1
    print("[PASS] File hygiene verified (scanned files compliant with line thresholds and asset policies).")
    return 0


def check_architectural_silos(root_dir: Path) -> int:
    """Verifies architectural silo invariants (planner is strictly siloed)."""
    graph = build_dependency_graph(root_dir)
    violations = verify_planner_silo(graph)
    if violations:
        print(f"[FAIL] Architectural silo violations detected ({len(violations)}):")
        for v in violations:
            print(f"  - {v}")
        return 1
    print("[PASS] Architectural silo invariants satisfied (planner strictly decoupled).")
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

    # 2. File hygiene & inline CSS/JS
    print("\n--- Gate 2: File Hygiene & Asset Policies ---")
    if check_hygiene(repo_root) != 0:
        return 1

    # 3. Type annotation completeness
    print("\n--- Gate 3: Type Annotation Completeness ---")
    if check_type_annotations(repo_root) != 0:
        return 1

    # 4. AST integrity and code hygiene
    print("\n--- Gate 4: AST Integrity and Code Hygiene ---")
    if check_ast(str(repo_root / "src")) != 0:
        return 1

    # 5. Architectural silos
    print("\n--- Gate 5: Architectural Silo Invariants ---")
    if check_architectural_silos(repo_root) != 0:
        return 1

    # 6. Ruff linting
    if run_command([sys.executable, "-m", "ruff", "check", "src/"], "Ruff Linter", repo_root) != 0:
        return 1

    # 7. Mypy static type checking
    if run_command([sys.executable, "-m", "mypy"], "Mypy Type Checker", repo_root) != 0:
        return 1

    # 8. Pytest test suite
    test_cmd = [sys.executable, "-m", "pytest", "-q"]
    if run_command(test_cmd, "Pytest Test Suite", repo_root) != 0:
        return 1

    print("\n====================================================================")
    print("[SUCCESS] All repository quality gates passed.")
    print("====================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
