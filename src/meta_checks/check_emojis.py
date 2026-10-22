"""
src/meta_checks/check_emojis.py

Verifies compliance with repository-wide Strict Emoji Ban across Python,
Markdown, and HTML files.
"""

from __future__ import annotations

import glob
import os
import re
import sys
from pathlib import Path

EMOJI_REGEX = re.compile(r"[\U00010000-\U0010ffff]")

TARGET_PATTERNS = [
    "src/**/*.py",
    "src/**/*.md",
    "src/**/*.html",
    "*.md",
]


def check_files(root_dir: str | Path | None = None) -> int:
    repo_root = Path(root_dir) if root_dir else Path(__file__).resolve().parents[2]
    files_to_check: set[Path] = set()

    for pattern in TARGET_PATTERNS:
        for match in repo_root.glob(pattern):
            if match.is_file():
                files_to_check.add(match)

    violations: list[Path] = []
    for filepath in sorted(files_to_check):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            if EMOJI_REGEX.search(content):
                violations.append(filepath)
        except Exception as ex:
            print(f"[WARN] Unable to inspect {filepath}: {ex}")

    if violations:
        print("[FAIL] Emoji ban violations detected in:")
        for v in violations:
            print(f"  - {v}")
        return 1

    print(f"[PASS] Zero emoji violations across {len(files_to_check)} files.")
    return 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(check_files(target))
