"""
src/meta_checks/check_ast.py

AST-based verification tool for detecting unused imports, undefined type annotations,
BOM markers, mutable default argument anti-patterns, and bare except clauses in Python code.
"""

from __future__ import annotations

import ast
import builtins
import sys
from pathlib import Path

COMMON_TYPING_SYMBOLS = {
    "List",
    "Dict",
    "Set",
    "Tuple",
    "Optional",
    "Union",
    "Any",
    "Callable",
    "Iterator",
    "Generator",
    "Sequence",
    "Iterable",
    "Mapping",
}


def extract_names_from_annotation_string(node_str: str) -> set[str]:
    """Parse stringified type annotations to extract referenced names."""
    try:
        sub_tree = ast.parse(node_str, mode="eval")
        return {n.id for n in ast.walk(sub_tree) if isinstance(n, ast.Name)}
    except Exception:
        return set()


def collect_used_names(tree: ast.AST) -> set[str]:
    """Collect all identifier names referenced across the AST."""
    used_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            used_names.update(extract_names_from_annotation_string(node.value))

    return used_names


def inspect_file(
    file_path: Path,
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    """
    Inspect a single Python file for:
    - UTF-8 BOM
    - Unused imports
    - Undefined type annotations
    - Mutable default arguments
    - Bare except clauses
    """
    bom_issues: list[str] = []
    unused_imports: list[str] = []
    undefined_annotations: list[str] = []
    mutable_defaults: list[str] = []
    bare_excepts: list[str] = []

    # Check for BOM
    with open(file_path, "rb") as raw_f:
        if raw_f.read(3) == b"\xef\xbb\xbf":
            bom_issues.append(f"{file_path}: File contains UTF-8 BOM marker.")

    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
        tree = ast.parse(content, filename=str(file_path))
    except Exception as exc:
        return bom_issues, [f"{file_path}: Syntax error - {exc}"], [], [], []

    is_init_file = file_path.name == "__init__.py"

    imported_names: dict[str, tuple[int, str]] = {}
    dunder_all_names: set[str] = set()
    defined_names: set[str] = set(dir(builtins))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_name = alias.asname or alias.name.split(".")[0]
                imported_names[imported_name] = (node.lineno, alias.name)
                defined_names.add(imported_name)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                imported_name = alias.asname or alias.name
                imported_names[imported_name] = (node.lineno, alias.name)
                defined_names.add(imported_name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined_names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined_names.add(node.id)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                dunder_all_names.add(elt.value)

        # Check for mutable defaults
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            all_defaults = [d for d in (node.args.defaults + node.args.kw_defaults) if d is not None]
            for default in all_defaults:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    mutable_defaults.append(
                        f"{file_path}:{node.lineno}: Mutable default argument in '{node.name}'"
                    )

        # Check for bare excepts and silent generic exception swallowing
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                bare_excepts.append(
                    f"{file_path}:{node.lineno}: Bare except clause detected."
                )
            elif isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"):
                non_trivial_stmts = [
                    s
                    for s in node.body
                    if not (
                        isinstance(s, ast.Pass)
                        or (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
                    )
                ]
                if not non_trivial_stmts:
                    bare_excepts.append(
                        f"{file_path}:{node.lineno}: Silent exception swallowing ('except {node.type.id}: pass')."
                    )

    used_names = collect_used_names(tree)

    # Check for undefined typing symbols in annotations or references
    for name in used_names:
        if name in COMMON_TYPING_SYMBOLS and name not in defined_names:
            undefined_annotations.append(
                f"{file_path}: Undefined typing annotation symbol '{name}' (missing from typing import)"
            )

    if not is_init_file:
        for name, (lineno, orig) in imported_names.items():
            if name not in used_names and name not in dunder_all_names:
                unused_imports.append(
                    f"{file_path}:{lineno}: Unused import '{name}' (imported as '{orig}')"
                )

    return bom_issues, unused_imports, undefined_annotations, mutable_defaults, bare_excepts


def run_checks(root_dir: str = "src") -> int:
    """Run all AST and encoding checks across the given directory."""
    target_path = Path(root_dir)
    py_files = sorted(target_path.rglob("*.py"))

    all_bom: list[str] = []
    all_unused: list[str] = []
    all_undefined: list[str] = []
    all_mutable: list[str] = []
    all_bare: list[str] = []

    for py_file in py_files:
        if "meta_checks" in py_file.parts:
            continue
        bom, unused, undefined, mutable, bare = inspect_file(py_file)
        all_bom.extend(bom)
        all_unused.extend(unused)
        all_undefined.extend(undefined)
        all_mutable.extend(mutable)
        all_bare.extend(bare)

    total_issues = (
        len(all_bom)
        + len(all_unused)
        + len(all_undefined)
        + len(all_mutable)
        + len(all_bare)
    )

    if all_bom:
        print("[ISSUE] UTF-8 BOM markers detected:")
        for item in all_bom:
            print(f"  - {item}")

    if all_undefined:
        print("[ISSUE] Undefined type annotations detected:")
        for item in all_undefined:
            print(f"  - {item}")

    if all_unused:
        print("[ISSUE] Unused imports detected:")
        for item in all_unused:
            print(f"  - {item}")

    if all_mutable:
        print("[ISSUE] Mutable default arguments detected:")
        for item in all_mutable:
            print(f"  - {item}")

    if all_bare:
        print("[ISSUE] Bare except clauses or silent exception swallowing detected:")
        for item in all_bare:
            print(f"  - {item}")

    if total_issues == 0:
        print(f"[PASS] AST inspection passed cleanly across {len(py_files)} files.")
        return 0

    print(f"[FAIL] Found {total_issues} code quality issues.")
    return 1


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "src"
    sys.exit(run_checks(target))
