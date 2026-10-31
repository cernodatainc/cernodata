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
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.meta_checks.check_ast import run_checks as check_ast
from src.meta_checks.check_emojis import check_files as check_emojis
from src.meta_checks.file_hygiene import run_meta_checks
from src.meta_checks.visualize_dependencies import build_dependency_graph, verify_planner_silo


class TypeInspector(ast.NodeVisitor):
    """Collects functions lacking complete type annotations into a shared issue list."""

    def __init__(self, filename: str, issues: list[tuple[str, int, str]]) -> None:
        self.filename = filename
        self.issues = issues

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_fn(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_fn(node)
        self.generic_visit(node)

    def _report(self, node: ast.FunctionDef | ast.AsyncFunctionDef, desc: str) -> None:
        self.issues.append((self.filename, node.lineno, f"{node.name}{desc}"))

    def _check_fn(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if node.returns is None:
            self._report(node, ": missing return type annotation")
        positional = [*node.args.posonlyargs, *node.args.args]
        for arg in positional:
            if arg.arg in ("self", "cls"):
                continue
            if arg.annotation is None:
                self._report(node, f"({arg.arg}): missing argument type annotation")
        for arg in node.args.kwonlyargs:
            if arg.annotation is None:
                self._report(node, f"({arg.arg}): missing kwonly argument type annotation")
        if node.args.vararg and node.args.vararg.annotation is None:
            self._report(node, f"(*{node.args.vararg.arg}): missing *args annotation")
        if node.args.kwarg and node.args.kwarg.annotation is None:
            self._report(node, f"(**{node.args.kwarg.arg}): missing **kwargs annotation")


def check_type_annotations(root_dir: Path) -> int:
    """Verifies that all functions and methods in non-test Python files have complete type annotations."""
    missing: list[tuple[str, int, str]] = []

    src_dir = root_dir / "src"
    for py_file in src_dir.rglob("*.py"):
        if "tests" in py_file.parts:
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            TypeInspector(str(py_file), missing).visit(tree)
        except (OSError, SyntaxError, UnicodeDecodeError) as ex:
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
    try:
        graph = build_dependency_graph(root_dir)
    except (OSError, SyntaxError, UnicodeDecodeError) as ex:
        print(f"[FAIL] Could not build dependency graph: {ex}")
        return 1
    violations = verify_planner_silo(graph)
    if violations:
        print(f"[FAIL] Architectural silo violations detected ({len(violations)}):")
        for v in violations:
            print(f"  - {v}")
        return 1
    print("[PASS] Architectural silo invariants satisfied (planner strictly decoupled).")
    return 0


def run_command(cmd: list[str], desc: str, cwd: Path) -> int:
    """Executes a command line tool and prints status."""
    print(f"\n--- Running: {desc} ({' '.join(cmd)}) ---")
    res = subprocess.run(cmd, cwd=cwd)
    if res.returncode != 0:
        print(f"[FAIL] {desc} returned non-zero exit code: {res.returncode}")
        return res.returncode
    print(f"[PASS] {desc} completed successfully.")
    return 0


def main() -> int:
    repo_root = REPO_ROOT

    print("====================================================================")
    print("cernodata Quality Verification Suite")
    print("====================================================================")

    # Static gates: (header, check callable). Tool gates below print their own headers.
    static_gates: list[tuple[str, Callable[[], int]]] = [
        ("Gate 1: Strict Emoji Ban Compliance", lambda: check_emojis(repo_root)),
        ("Gate 2: File Hygiene & Asset Policies", lambda: check_hygiene(repo_root)),
        ("Gate 3: Type Annotation Completeness", lambda: check_type_annotations(repo_root)),
        ("Gate 4: AST Integrity and Code Hygiene", lambda: check_ast(str(repo_root / "src"))),
        ("Gate 5: Architectural Silo Invariants", lambda: check_architectural_silos(repo_root)),
    ]
    for header, gate in static_gates:
        print(f"\n--- {header} ---")
        if gate() != 0:
            return 1

    tool_gates: list[tuple[list[str], str]] = [
        ([sys.executable, "-m", "ruff", "check", "src/"], "Ruff Linter"),
        ([sys.executable, "-m", "mypy"], "Mypy Type Checker"),
        ([sys.executable, "-m", "pytest", "-q"], "Pytest Test Suite"),
    ]
    for cmd, desc in tool_gates:
        if run_command(cmd, desc, repo_root) != 0:
            return 1

    print("\n====================================================================")
    print("[SUCCESS] All repository quality gates passed.")
    print("====================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
