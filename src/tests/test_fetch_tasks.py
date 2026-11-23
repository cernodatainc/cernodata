"""
src/tests/test_fetch_tasks.py

Unit tests for src/fetch_tasks.py:
- GitHub remote URL parsing and token resolution.
- Pagination via Link headers and pull-request filtering.
- Single issue retrieval and error handling.
- Formatting (text, markdown, JSON) and markdown file export.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from unittest.mock import patch

from src.fetch_tasks import (
    DEFAULT_OUTPUT_DIR,
    TaskIssue,
    _parse_next_link,
    build_parser,
    export_issues_markdown,
    fetch_issue,
    fetch_issues,
    format_issue_markdown,
    format_issues_text,
    main,
    parse_github_repo_from_remote,
    resolve_token,
    slugify_title,
)


def _sample_issue_payload(
    number: int = 1,
    title: str = "Implement OCR fallback",
    state: str = "open",
    is_pr: bool = False,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "number": number,
        "title": title,
        "state": state,
        "html_url": f"https://github.com/cernodatainc/cernodata/issues/{number}",
        "body": f"Details for issue #{number}.",
        "labels": [{"name": "task"}, {"name": "pipeline"}],
        "assignees": [{"login": "alice"}],
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
    }
    if is_pr:
        payload["pull_request"] = {"url": f"https://api.github.com/repos/cernodatainc/cernodata/pulls/{number}"}
    return payload


class TestFetchTasks(unittest.TestCase):
    def test_parse_github_repo_from_remote_https_and_ssh(self) -> None:
        self.assertEqual(
            parse_github_repo_from_remote("https://github.com/cernodatainc/cernodata.git"),
            "cernodatainc/cernodata",
        )
        self.assertEqual(
            parse_github_repo_from_remote("https://github.com/cernodatainc/cernodata/"),
            "cernodatainc/cernodata",
        )
        self.assertEqual(
            parse_github_repo_from_remote("git@github.com:cernodatainc/cernodata.git"),
            "cernodatainc/cernodata",
        )
        self.assertIsNone(parse_github_repo_from_remote("https://gitlab.com/org/repo.git"))

    def test_resolve_token_precedence(self) -> None:
        with patch.dict(os.environ, {"GITHUB_TOKEN": "env_gh", "GH_TOKEN": "env_cli"}, clear=True):
            self.assertEqual(resolve_token("explicit_tok"), "explicit_tok")
            self.assertEqual(resolve_token(None), "env_gh")

        with patch.dict(os.environ, {"GH_TOKEN": "env_cli"}, clear=True):
            self.assertEqual(resolve_token(None), "env_cli")

        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(resolve_token(None))

    def test_parse_next_link(self) -> None:
        header = (
            '<https://api.github.com/repositories/1/issues?page=2>; rel="next", '
            '<https://api.github.com/repositories/1/issues?page=5>; rel="last"'
        )
        self.assertEqual(
            _parse_next_link(header),
            "https://api.github.com/repositories/1/issues?page=2",
        )
        self.assertIsNone(_parse_next_link('<https://api.github.com/repositories/1/issues?page=1>; rel="prev"'))
        self.assertIsNone(_parse_next_link(None))

    def test_fetch_issues_paginates_and_filters_pull_requests(self) -> None:
        page_1_url = "https://api.github.com/repos/cernodatainc/cernodata/issues?state=open&per_page=100&sort=created&direction=asc"
        page_2_url = "https://api.github.com/repos/cernodatainc/cernodata/issues?page=2"

        responses: Dict[str, Tuple[Any, Optional[str]]] = {
            page_1_url: (
                [
                    _sample_issue_payload(1, "First task"),
                    _sample_issue_payload(2, "A pull request", is_pr=True),
                ],
                page_2_url,
            ),
            page_2_url: (
                [_sample_issue_payload(3, "Second task")],
                None,
            ),
        }

        def fake_get(url: str, token: Optional[str] = None, timeout: int = 30) -> Tuple[Any, Optional[str]]:
            return responses[url]

        with patch("src.fetch_tasks._http_get_json", side_effect=fake_get):
            issues = fetch_issues("cernodatainc/cernodata", state="open")

        self.assertEqual([i.number for i in issues], [1, 3])
        self.assertEqual(issues[0].labels, ("task", "pipeline"))
        self.assertEqual(issues[0].assignees, ("alice",))

    def test_fetch_issue_rejects_pull_request(self) -> None:
        pr_payload = _sample_issue_payload(17, "PR title", is_pr=True)
        with patch("src.fetch_tasks._http_get_json", return_value=(pr_payload, None)):
            with self.assertRaises(RuntimeError) as ctx:
                fetch_issue("cernodatainc/cernodata", 17)
        self.assertIn("pull request", str(ctx.exception))

    def test_slugify_and_export_markdown(self) -> None:
        self.assertEqual(slugify_title("Fix: Table Grid / Layout!"), "fix-table-grid-layout")
        self.assertEqual(slugify_title("   "), "issue")

        issue = TaskIssue(
            number=42,
            title="Add Benchmark Harness",
            state="open",
            url="https://github.com/cernodatainc/cernodata/issues/42",
            body="Run nightly benchmarks.",
            labels=("perf",),
            assignees=("bob",),
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-02T00:00:00Z",
        )

        with tempfile.TemporaryDirectory() as tmp:
            written = export_issues_markdown([issue], Path(tmp))
            self.assertEqual(len(written), 1)
            self.assertEqual(written[0].name, "0042-add-benchmark-harness.md")
            content = written[0].read_text(encoding="utf-8")
            self.assertIn("# #42: Add Benchmark Harness", content)
            self.assertIn("Run nightly benchmarks.", content)

    def test_format_helpers_and_cli_json_output(self) -> None:
        issue = TaskIssue(
            number=7,
            title="Support Polish Diacritics",
            state="open",
            url="https://github.com/cernodatainc/cernodata/issues/7",
            body="Line one\nLine two",
            labels=("ocr",),
            assignees=(),
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-02T00:00:00Z",
        )
        self.assertEqual(format_issues_text([]), "No matching GitHub issues found.")
        text_out = format_issues_text([issue], include_body=True)
        self.assertIn("#7 (open) [ocr]: Support Polish Diacritics", text_out)
        self.assertIn("| Line one", text_out)
        self.assertIn("Unassigned", format_issue_markdown(issue))

        stdout_buf = io.StringIO()
        with (
            patch("src.fetch_tasks.fetch_issues", return_value=[issue]),
            patch("sys.stdout", stdout_buf),
        ):
            rc = main(["--repo", "cernodatainc/cernodata", "--stdout", "--format", "json"])

        self.assertEqual(rc, 0)
        parsed = json.loads(stdout_buf.getvalue())
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["number"], 7)

    def test_cli_saves_to_output_dir_by_default(self) -> None:
        self.assertEqual(build_parser().parse_args([]).output_dir, DEFAULT_OUTPUT_DIR)
        self.assertEqual(DEFAULT_OUTPUT_DIR, "src/tasks")

        issue = TaskIssue(
            number=12,
            title="Default Save Check",
            state="open",
            url="https://github.com/cernodatainc/cernodata/issues/12",
            body="Body text.",
            labels=(),
            assignees=(),
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-02T00:00:00Z",
        )
        stdout_buf = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch("src.fetch_tasks.fetch_issues", return_value=[issue]),
                patch("sys.stdout", stdout_buf),
            ):
                rc = main(["--repo", "cernodatainc/cernodata", "--output-dir", tmp])

            self.assertEqual(rc, 0)
            saved_files = list(Path(tmp).glob("*.md"))
            self.assertEqual(len(saved_files), 1)
            self.assertEqual(saved_files[0].name, "0012-default-save-check.md")
            self.assertIn("Saved 1 issue(s)", stdout_buf.getvalue())

    def test_cli_returns_nonzero_on_error(self) -> None:
        stderr_buf = io.StringIO()
        with (
            patch("src.fetch_tasks.fetch_issues", side_effect=RuntimeError("API down")),
            patch("sys.stderr", stderr_buf),
        ):
            rc = main(["--repo", "cernodatainc/cernodata"])

        self.assertEqual(rc, 1)
        self.assertIn("API down", stderr_buf.getvalue())


if __name__ == "__main__":
    unittest.main()
