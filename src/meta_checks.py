"""
src/meta_checks.py

Repository meta-quality enforcement checks.
Surfaces the longest source files and flags anything exceeding 500 lines.
Flags inline CSS and inline JS unless explicitly muted with substantive justification.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

DEFAULT_WARN_LINES: int = 250
DEFAULT_MAX_LINES: int = 500
MIN_JUSTIFICATION_LENGTH: int = 15

BANNED_JUSTIFICATIONS: Set[str] = {
    "todo", "fixme", "skip", "ignore", "temp", "temporary", "none",
    "n/a", "na", "test", "testing", "just because", "allow", "bypass",
}

DEFAULT_EXCLUDE_DIRS: Set[str] = {
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".venv", "output", "test_output", "dist", "build", "node_modules",
}

BINARY_EXTENSIONS: Set[str] = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2",
    ".ttf", ".eot", ".zip", ".tar", ".gz", ".pyc", ".pyo", ".pyd", ".so",
    ".dll", ".exe",
}


@dataclass(frozen=True)
class FileInfo:
    """Information describing a scanned file and its line count."""
    path: str
    rel_path: str
    line_count: int


@dataclass(frozen=True)
class FileLengthWarning:
    """Warning record for a file in the yellow-flag range (warn_lines to max_lines)."""
    file: FileInfo
    warn_threshold: int
    max_threshold: int
    message: str


@dataclass(frozen=True)
class FileLengthViolation:
    """Violation record for a file exceeding maximum permitted lines."""
    file: FileInfo
    threshold: int
    message: str


@dataclass(frozen=True)
class InlineViolation:
    """Violation record for inline CSS or inline JS code."""
    file_path: str
    rel_path: str
    line_number: int
    violation_type: str
    snippet: str
    message: str


@dataclass(frozen=True)
class MutedCase:
    """Configuration record permitting an exception when substantiated with justification."""
    file_pattern: str
    violation_type: str
    justification: str
    line_number: Optional[int] = None

    def is_valid_justification(self, min_length: int = MIN_JUSTIFICATION_LENGTH) -> bool:
        cleaned = self.justification.strip()
        return len(cleaned) >= min_length and cleaned.lower() not in BANNED_JUSTIFICATIONS

    def matches(self, rel_path: str, viol_type: str, line_no: Optional[int] = None) -> bool:
        norm_path = rel_path.replace("\\", "/")
        norm_pattern = self.file_pattern.replace("\\", "/")
        if norm_pattern != "*" and norm_pattern not in norm_path:
            return False

        if self.violation_type not in ("*", "all", viol_type):
            type_groups = {
                "inline_css": {"inline_style_tag", "inline_style_attribute"},
                "inline_js": {"inline_script_tag", "inline_event_handler"},
            }
            if viol_type not in type_groups.get(self.violation_type, set()):
                return False

        if self.line_number is not None and line_no is not None and self.line_number != line_no:
            return False
        return True


DEFAULT_MUTED_CASES: List[MutedCase] = [
    MutedCase(
        file_pattern="src/visualization/viewer/template.html",
        violation_type="inline_style_tag",
        justification="Standalone offline HTML export requires inlining CSS bundle so the artifact works without external assets.",
    ),
    MutedCase(
        file_pattern="src/visualization/viewer/template.html",
        violation_type="inline_script_tag",
        justification="Standalone offline HTML export requires inlining JavaScript runtime and payload for zero-dependency usage.",
    ),
    MutedCase(
        file_pattern="src/visualization/viewer/html/canvas.html",
        violation_type="inline_style_attribute",
        justification="Dynamic server-side template color placeholder injection in canvas overlay component.",
    ),
    MutedCase(
        file_pattern="src/visualization/viewer/viewer.css",
        violation_type="file_length",
        justification="Monolithic visual flow viewer stylesheet pending modular component breakdown.",
    ),
    MutedCase(
        file_pattern="src/visualization/landing.css",
        violation_type="file_length",
        justification="Monolithic pipeline landing dashboard stylesheet pending modular component breakdown.",
    ),
    MutedCase(
        file_pattern="src/visualization/data_shape_config.css",
        violation_type="file_length",
        justification="Monolithic planner wizard stylesheet pending modular component breakdown.",
    ),
    MutedCase(
        file_pattern="src/visualization/viewer/js/state.js",
        violation_type="file_length",
        justification="Central viewer state container with DOM diffing, dynamic score recalculation, and hydration routines.",
    ),
    MutedCase(
        file_pattern="src/visualization/viewer/js/decollide.js",
        violation_type="file_length",
        justification="Pairwise bounding box decollision, multi-node overlap inspection, and element merge editor.",
    ),
]


def scan_file_lengths(
    target_dir: str,
    extensions: Optional[Sequence[str]] = None,
    exclude_dirs: Optional[Sequence[str]] = None,
) -> List[FileInfo]:
    """Scans files in target directory and returns their line counts sorted descending."""
    excluded = set(exclude_dirs) if exclude_dirs is not None else DEFAULT_EXCLUDE_DIRS
    ext_filter = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions} if extensions else None
    results: List[FileInfo] = []
    base_dir = os.path.abspath(target_dir)

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in excluded]
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in BINARY_EXTENSIONS or (ext_filter is not None and ext not in ext_filter):
                continue
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, base_dir).replace("\\", "/")
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as fp:
                    count = sum(1 for _ in fp)
                results.append(FileInfo(path=full_path, rel_path=rel_path, line_count=count))
            except OSError:
                continue

    results.sort(key=lambda item: item.line_count, reverse=True)
    return results


def surface_longest_files(
    target_dir: str,
    top_n: int = 10,
    warn_lines: int = DEFAULT_WARN_LINES,
    max_lines: int = DEFAULT_MAX_LINES,
    extensions: Optional[Sequence[str]] = None,
    exclude_dirs: Optional[Sequence[str]] = None,
) -> Tuple[List[FileInfo], str]:
    """Surfaces top N longest files in directory and formats a summary report."""
    scanned = scan_file_lengths(target_dir, extensions=extensions, exclude_dirs=exclude_dirs)
    top_files = scanned[:top_n]
    lines: List[str] = [
        f"Top {len(top_files)} Longest Files in '{target_dir}':",
        "-" * 72,
    ]
    for idx, item in enumerate(top_files, 1):
        if item.line_count > max_lines:
            flag = "[RED FLAG]"
        elif item.line_count >= warn_lines:
            flag = "[YELLOW FLAG]"
        else:
            flag = "[OK]"
        lines.append(f"{idx:2d}. {item.line_count:5d} lines | {flag:<13} | {item.rel_path}")
    lines.append("-" * 72)
    return top_files, "\n".join(lines)


def check_file_length_warnings(
    target_dir: str,
    warn_lines: int = DEFAULT_WARN_LINES,
    max_lines: int = DEFAULT_MAX_LINES,
    extensions: Optional[Sequence[str]] = None,
    exclude_dirs: Optional[Sequence[str]] = None,
) -> List[FileLengthWarning]:
    """Surfaces files in the yellow flag zone (between warn_lines and max_lines)."""
    all_files = scan_file_lengths(target_dir, extensions=extensions, exclude_dirs=exclude_dirs)
    warnings: List[FileLengthWarning] = []
    for item in all_files:
        if warn_lines <= item.line_count <= max_lines:
            warnings.append(FileLengthWarning(
                file=item,
                warn_threshold=warn_lines,
                max_threshold=max_lines,
                message=(
                    f"File '{item.rel_path}' has {item.line_count} lines "
                    f"(yellow flag: {warn_lines}-{max_lines} lines; approaching {max_lines} limit)."
                ),
            ))
    return warnings


def check_file_lengths(
    target_dir: str,
    max_lines: int = DEFAULT_MAX_LINES,
    extensions: Optional[Sequence[str]] = None,
    exclude_dirs: Optional[Sequence[str]] = None,
    muted_cases: Optional[Sequence[MutedCase]] = None,
    top_n: int = 10,
) -> Tuple[List[FileInfo], List[FileLengthViolation]]:
    """Surfaces the longest files and flags any exceeding max_lines unless validly muted."""
    all_files = scan_file_lengths(target_dir, extensions=extensions, exclude_dirs=exclude_dirs)
    longest_files = all_files[:top_n]
    mutes = list(muted_cases) if muted_cases is not None else []
    violations: List[FileLengthViolation] = []

    for item in all_files:
        if item.line_count <= max_lines:
            continue
        matched_mute = next((m for m in mutes if m.matches(item.rel_path, "file_length")), None)
        if matched_mute is not None:
            if not matched_mute.is_valid_justification():
                violations.append(FileLengthViolation(
                    file=item, threshold=max_lines,
                    message=(
                        f"File '{item.rel_path}' exceeds {max_lines} lines ({item.line_count} lines) "
                        f"and has an invalid/trivial mute justification: '{matched_mute.justification}'"
                    ),
                ))
            continue

        violations.append(FileLengthViolation(
            file=item, threshold=max_lines,
            message=f"File '{item.rel_path}' exceeds threshold of {max_lines} lines ({item.line_count} lines).",
        ))

    return longest_files, violations


def _extract_comment_mutes(content: str) -> List[Tuple[int, str, str]]:
    directives: List[Tuple[int, str, str]] = []
    pattern = re.compile(
        r"(?:<!--|/\*|//|#)\s*meta:(?:allow|mute)[:-]?(inline[-_]css|inline[-_]js|all)[:\s]+(.*?)(?:-->|\*/)?$",
        re.IGNORECASE,
    )
    for line_idx, line in enumerate(content.splitlines(), start=1):
        m = pattern.search(line.strip())
        if m:
            t_type = m.group(1).lower().replace("-", "_")
            just = m.group(2).strip().rstrip("-*>")
            directives.append((line_idx, t_type, just))
    return directives


def scan_inline_css_and_js(
    target_dir: str,
    extensions: Optional[Sequence[str]] = (".html", ".htm", ".svg"),
    include_event_handlers: bool = True,
    exclude_dirs: Optional[Sequence[str]] = None,
) -> List[InlineViolation]:
    """Scans files in target directory for inline CSS and inline JS occurrences."""
    excluded = set(exclude_dirs) if exclude_dirs is not None else DEFAULT_EXCLUDE_DIRS
    target_exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in (extensions or [".html", ".htm"])}
    violations: List[InlineViolation] = []
    base_dir = os.path.abspath(target_dir)

    style_tag_re = re.compile(r"<style\b[^>]*>(.*?)</style>", re.DOTALL | re.IGNORECASE)
    script_tag_re = re.compile(r"<script\b(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)
    style_attr_re = re.compile(r"""\bstyle\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
    event_attr_re = re.compile(r"""\b(on[a-z]{3,20})\s*=\s*["']([^"']+)["']""", re.IGNORECASE)

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in excluded]
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in target_exts:
                continue
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, base_dir).replace("\\", "/")
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read()
            except OSError:
                continue

            lines = content.splitlines(keepends=True)

            def get_line_no(char_idx: int) -> int:
                curr = 0
                for idx, line_s in enumerate(lines, start=1):
                    curr += len(line_s)
                    if curr > char_idx:
                        return idx
                return len(lines)

            for m in style_tag_re.finditer(content):
                if m.group(1).strip():
                    lno = get_line_no(m.start())
                    violations.append(InlineViolation(
                        full_path, rel_path, lno, "inline_style_tag",
                        m.group(1).strip()[:60].replace("\n", " "),
                        f"Inline <style> tag detected at {rel_path}:{lno}.",
                    ))

            for m in script_tag_re.finditer(content):
                if m.group(1).strip():
                    lno = get_line_no(m.start())
                    violations.append(InlineViolation(
                        full_path, rel_path, lno, "inline_script_tag",
                        m.group(1).strip()[:60].replace("\n", " "),
                        f"Inline <script> tag detected at {rel_path}:{lno}.",
                    ))

            for lidx, lstr in enumerate(lines, start=1):
                for sm in style_attr_re.finditer(lstr):
                    violations.append(InlineViolation(
                        full_path, rel_path, lidx, "inline_style_attribute",
                        sm.group(0)[:60], f"Inline style attribute detected at {rel_path}:{lidx}.",
                    ))
                if include_event_handlers:
                    for em in event_attr_re.finditer(lstr):
                        violations.append(InlineViolation(
                            full_path, rel_path, lidx, "inline_event_handler",
                            em.group(0)[:60], f"Inline event handler '{em.group(1)}' at {rel_path}:{lidx}.",
                        ))

    return violations


def check_inline_css_and_js(
    target_dir: str,
    muted_cases: Optional[Sequence[MutedCase]] = None,
    extensions: Optional[Sequence[str]] = (".html", ".htm", ".svg"),
    include_event_handlers: bool = False,
    exclude_dirs: Optional[Sequence[str]] = None,
) -> List[InlineViolation]:
    """Flags inline CSS and inline JS occurrences unless explicitly muted with substantive justification."""
    raw = scan_inline_css_and_js(target_dir, extensions, include_event_handlers, exclude_dirs)
    mutes = list(muted_cases) if muted_cases is not None else []
    active: List[InlineViolation] = []
    file_comments: Dict[str, List[Tuple[int, str, str]]] = {}

    for viol in raw:
        matched = next((m for m in mutes if m.matches(viol.rel_path, viol.violation_type, viol.line_number)), None)
        if matched is not None:
            if not matched.is_valid_justification():
                active.append(InlineViolation(
                    viol.file_path, viol.rel_path, viol.line_number, viol.violation_type, viol.snippet,
                    f"{viol.message} Exception muted, but justification is invalid/trivial: '{matched.justification}'",
                ))
            continue

        if viol.file_path not in file_comments:
            try:
                with open(viol.file_path, "r", encoding="utf-8", errors="ignore") as fp:
                    file_comments[viol.file_path] = _extract_comment_mutes(fp.read())
            except OSError:
                file_comments[viol.file_path] = []

        matched_comment = None
        for d_line, d_type, d_just in file_comments[viol.file_path]:
            type_match = (
                d_type in ("all", viol.violation_type)
                or (d_type == "inline_css" and viol.violation_type in ("inline_style_tag", "inline_style_attribute"))
                or (d_type == "inline_js" and viol.violation_type in ("inline_script_tag", "inline_event_handler"))
            )
            if type_match and (d_line <= 5 or abs(viol.line_number - d_line) <= 2):
                matched_comment = (d_line, d_type, d_just)
                break

        if matched_comment is not None:
            _, _, just_text = matched_comment
            if not MutedCase("*", "*", just_text).is_valid_justification():
                active.append(InlineViolation(
                    viol.file_path, viol.rel_path, viol.line_number, viol.violation_type, viol.snippet,
                    f"{viol.message} In-file comment mute has invalid/trivial justification: '{just_text}'",
                ))
            continue

        active.append(viol)

    return active


def run_meta_checks(
    target_dir: Optional[str] = None,
    max_lines: int = DEFAULT_MAX_LINES,
    warn_lines: int = DEFAULT_WARN_LINES,
    muted_cases: Optional[Sequence[MutedCase]] = None,
    include_event_handlers: bool = False,
) -> Dict[str, Any]:
    """Executes all meta quality checks against target directory."""
    base_dir = target_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mutes = muted_cases if muted_cases is not None else DEFAULT_MUTED_CASES
    longest_files, length_viols = check_file_lengths(base_dir, max_lines, muted_cases=mutes)
    inline_viols = check_inline_css_and_js(base_dir, muted_cases=mutes, include_event_handlers=include_event_handlers)
    yellow_flags = check_file_length_warnings(base_dir, warn_lines=warn_lines, max_lines=max_lines)

    return {
        "is_passed": (len(length_viols) == 0 and len(inline_viols) == 0),
        "target_dir": base_dir,
        "max_lines": max_lines,
        "warn_lines": warn_lines,
        "longest_files": [{"path": f.rel_path, "lines": f.line_count} for f in longest_files],
        "yellow_flags": [
            {"file": w.file.rel_path, "lines": w.file.line_count, "threshold": w.warn_threshold, "message": w.message}
            for w in yellow_flags
        ],
        "length_violations": [
            {"file": v.file.rel_path, "lines": v.file.line_count, "threshold": v.threshold, "message": v.message}
            for v in length_viols
        ],
        "inline_violations": [
            {"file": v.rel_path, "line": v.line_number, "type": v.violation_type, "snippet": v.snippet, "message": v.message}
            for v in inline_viols
        ],
    }


__all__ = [
    "DEFAULT_WARN_LINES", "DEFAULT_MAX_LINES", "MIN_JUSTIFICATION_LENGTH", "DEFAULT_MUTED_CASES",
    "FileInfo", "FileLengthWarning", "FileLengthViolation", "InlineViolation", "MutedCase",
    "scan_file_lengths", "surface_longest_files", "check_file_lengths",
    "check_file_length_warnings",
    "scan_inline_css_and_js", "check_inline_css_and_js", "run_meta_checks",
]


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Repository meta-quality and file-length enforcement.")
    parser.add_argument("target_dir", nargs="?", default=None, help="Root directory to scan (default: repository root)")
    parser.add_argument("--warn", type=int, default=DEFAULT_WARN_LINES, help="Yellow-flag warning threshold (default: 250)")
    parser.add_argument("--max", type=int, default=DEFAULT_MAX_LINES, help="Red-flag error threshold (default: 500)")
    parser.add_argument("--top", type=int, default=10, help="Number of longest files to surface (default: 10)")
    parser.add_argument("--yellow-only", action="store_true", help="Display only yellow-flag files (250-500 lines)")
    args = parser.parse_args()

    root = args.target_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if args.yellow_only:
        yfs = check_file_length_warnings(root, warn_lines=args.warn, max_lines=args.max)
        print(f"Yellow Flag Files ({len(yfs)} files between {args.warn} and {args.max} lines):")
        print("-" * 72)
        for yf in yfs:
            print(f"  {yf.file.line_count:4d} lines | {yf.file.rel_path}")
        print("-" * 72)
        sys.exit(0)

    _, longest_report = surface_longest_files(root, top_n=args.top, warn_lines=args.warn, max_lines=args.max)
    print(longest_report)
    print()

    res = run_meta_checks(root, max_lines=args.max, warn_lines=args.warn)
    print("Meta Checks Status:", "PASSED" if res["is_passed"] else "FAILED")
    if res["yellow_flags"]:
        print(f"\nYellow Flags ({len(res['yellow_flags'])} files in {args.warn}-{args.max} line range):")
        for yf in res["yellow_flags"]:
            print(f"  - [YELLOW FLAG] {yf['file']} ({yf['lines']} lines)")
    if res["length_violations"]:
        print(f"\nFile Length Violations ({len(res['length_violations'])}):")
        for lv in res["length_violations"]:
            print(f"  - [RED FLAG] {lv['message']}")
    if res["inline_violations"]:
        print(f"\nInline CSS/JS Violations ({len(res['inline_violations'])}):")
        for iv in res["inline_violations"]:
            print(f"  - {iv['message']}")
    sys.exit(0 if res["is_passed"] else 1)

