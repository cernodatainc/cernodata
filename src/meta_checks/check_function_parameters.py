"""
src/meta_checks/check_function_parameters.py

AST-based code hygiene checker enforcing function parameter layout:
Either all function parameters are on the same line (under the 120 character limit)
or all parameters are on different lines.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Sequence

DEFAULT_MAX_LINE_LENGTH: int = 120


def _get_function_parameters(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[tuple[ast.arg, ast.expr | None]]:
    """Collects (ast.arg, default_expr | None) for all parameters in declaration order."""
    params: list[tuple[ast.arg, ast.expr | None]] = []

    all_pos = [*node.args.posonlyargs, *node.args.args]
    num_defaults = len(node.args.defaults)
    pos_defaults: list[ast.expr | None] = [None] * (len(all_pos) - num_defaults) + list(node.args.defaults)

    for arg, default in zip(all_pos, pos_defaults):
        params.append((arg, default))

    if node.args.vararg is not None:
        params.append((node.args.vararg, None))

    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        params.append((arg, default))

    if node.args.kwarg is not None:
        params.append((node.args.kwarg, None))

    return params


def _get_param_span(arg: ast.arg, default: ast.expr | None) -> tuple[int, int]:
    """Calculates the (start_lineno, end_lineno) span of a parameter including defaults and annotations."""
    start_line = arg.lineno
    end_line = arg.end_lineno if arg.end_lineno is not None else arg.lineno

    if arg.annotation is not None:
        ann_end = arg.annotation.end_lineno if arg.annotation.end_lineno is not None else arg.annotation.lineno
        end_line = max(end_line, ann_end)

    if default is not None:
        def_end = default.end_lineno if default.end_lineno is not None else default.lineno
        end_line = max(end_line, def_end)

    return start_line, end_line


def inspect_source(
    content: str,
    filename: str = "<string>",
    max_line_length: int = DEFAULT_MAX_LINE_LENGTH,
) -> list[str]:
    """Inspects Python source string for function parameter layout compliance."""
    try:
        tree = ast.parse(content, filename=filename)
    except (SyntaxError, UnicodeDecodeError) as ex:
        return [f"{filename}:0: Syntax error parsing source: {ex}"]

    lines = content.splitlines()
    issues: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        params = _get_function_parameters(node)
        if not params:
            continue

        spans = [_get_param_span(arg, default) for arg, default in params]

        if len(params) == 1:
            start_l, end_l = spans[0]
            if start_l == end_l:
                if start_l <= len(lines) and len(lines[start_l - 1]) > max_line_length:
                    issues.append(
                        f"{filename}:{start_l}: Function '{node.name}' has single parameter on line {start_l} "
                        f"exceeding {max_line_length} characters ({len(lines[start_l - 1])} chars)."
                    )
                elif (
                    node.lineno == start_l
                    and node.lineno <= len(lines)
                    and len(lines[node.lineno - 1]) > max_line_length
                ):
                    issues.append(
                        f"{filename}:{node.lineno}: Function '{node.name}' definition line {node.lineno} "
                        f"exceeding {max_line_length} characters ({len(lines[node.lineno - 1])} chars)."
                    )
            continue

        all_same_line = all(s == spans[0][0] and e == spans[0][0] for s, e in spans)

        if all_same_line:
            param_line = spans[0][0]
            line_len = len(lines[param_line - 1]) if param_line <= len(lines) else 0
            def_len = len(lines[node.lineno - 1]) if node.lineno <= len(lines) else 0

            if line_len > max_line_length:
                issues.append(
                    f"{filename}:{node.lineno}: Function '{node.name}' parameters are all on line {param_line}, "
                    f"but line exceeds {max_line_length} characters ({line_len} chars). "
                    "Must be split so all parameters are on different lines."
                )
            elif node.lineno != param_line and def_len > max_line_length:
                issues.append(
                    f"{filename}:{node.lineno}: Function '{node.name}' header line exceeds {max_line_length} "
                    f"characters ({def_len} chars)."
                )
            continue

        # Check if all parameters are on different lines
        start_lines = [s for s, _ in spans]
        if len(set(start_lines)) != len(params):
            issues.append(
                f"{filename}:{node.lineno}: Function '{node.name}' parameters must either all be on the same "
                f"line (<={max_line_length} chars) or all on different lines; found multiple parameters sharing line(s)."
            )
            continue

        overlapping = False
        for i in range(len(spans) - 1):
            curr_end = spans[i][1]
            next_start = spans[i + 1][0]
            if next_start <= curr_end:
                issues.append(
                    f"{filename}:{node.lineno}: Function '{node.name}' parameters must all be on different lines; "
                    f"parameter '{params[i + 1][0].arg}' on line {next_start} overlaps with parameter "
                    f"'{params[i][0].arg}' ending on line {curr_end}."
                )
                overlapping = True
                break

        if not overlapping:
            # Verify no parameter line itself exceeds max_line_length
            for i, (s, e) in enumerate(spans):
                for l_no in range(s, e + 1):
                    if l_no <= len(lines) and len(lines[l_no - 1]) > max_line_length:
                        issues.append(
                            f"{filename}:{l_no}: Function '{node.name}' parameter '{params[i][0].arg}' line {l_no} "
                            f"exceeds {max_line_length} characters ({len(lines[l_no - 1])} chars)."
                        )

    return issues


def inspect_file(
    file_path: Path | str,
    max_line_length: int = DEFAULT_MAX_LINE_LENGTH,
) -> list[str]:
    """Inspects a single Python file for function parameter layout compliance."""
    path = Path(file_path)
    try:
        content = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as ex:
        return [f"{path}:0: Unable to read file: {ex}"]

    return inspect_source(content, filename=str(path), max_line_length=max_line_length)


def check_files(
    target_dir: str | Path = "src",
    max_line_length: int = DEFAULT_MAX_LINE_LENGTH,
    exclude_dirs: Sequence[str] = ("meta_checks",),
) -> int:
    """Scans Python files under target_dir and verifies parameter layout compliance."""
    root = Path(target_dir)
    py_files = sorted(root.rglob("*.py")) if root.is_dir() else [root]

    all_issues: list[str] = []
    scanned_count = 0

    for py_file in py_files:
        if any(ex in py_file.parts for ex in exclude_dirs):
            continue
        scanned_count += 1
        issues = inspect_file(py_file, max_line_length=max_line_length)
        all_issues.extend(issues)

    if all_issues:
        print(f"[FAIL] Found {len(all_issues)} function parameter layout violations:")
        for issue in all_issues:
            print(f"  - {issue}")
        return 1

    print(f"[PASS] All function parameters compliant across {scanned_count} files.")
    return 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "src"
    sys.exit(check_files(target))
