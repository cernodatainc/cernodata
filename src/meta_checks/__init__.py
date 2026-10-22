"""
src/meta_checks package.

Consolidated repository quality enforcement, hygiene verification,
emoji compliance, dependency analysis, and gate runner suite.
"""

from src.meta_checks.file_hygiene import (
    DEFAULT_WARN_LINES,
    DEFAULT_MAX_LINES,
    MIN_JUSTIFICATION_LENGTH,
    DEFAULT_MUTED_CASES,
    FileInfo,
    FileLengthWarning,
    FileLengthViolation,
    InlineViolation,
    MutedCase,
    scan_file_lengths,
    surface_longest_files,
    check_file_lengths,
    check_file_length_warnings,
    scan_inline_css_and_js,
    check_inline_css_and_js,
    run_meta_checks,
)

__all__ = [
    "DEFAULT_WARN_LINES",
    "DEFAULT_MAX_LINES",
    "MIN_JUSTIFICATION_LENGTH",
    "DEFAULT_MUTED_CASES",
    "FileInfo",
    "FileLengthWarning",
    "FileLengthViolation",
    "InlineViolation",
    "MutedCase",
    "scan_file_lengths",
    "surface_longest_files",
    "check_file_lengths",
    "check_file_length_warnings",
    "scan_inline_css_and_js",
    "check_inline_css_and_js",
    "run_meta_checks",
]
