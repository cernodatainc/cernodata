"""
src/fetch_tasks.py

Fetches project tasks stored as GitHub issues for the repository.
Supports listing issues, inspecting a single issue, filtering by state or
labels, formatting as text/markdown/json, and optionally exporting to files.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

DEFAULT_REPO: str = "cernodatainc/cernodata"
DEFAULT_OUTPUT_DIR: str = "src/tasks"
GITHUB_API_BASE: str = "https://api.github.com"
DEFAULT_PER_PAGE: int = 100
REQUEST_TIMEOUT_SECONDS: int = 30


@dataclass(frozen=True)
class TaskIssue:
    """Normalized representation of a GitHub issue representing a task."""

    number: int
    title: str
    state: str
    url: str
    body: str
    labels: Tuple[str, ...]
    assignees: Tuple[str, ...]
    created_at: str
    updated_at: str


def parse_github_repo_from_remote(remote_url: str) -> Optional[str]:
    """Extracts 'owner/repo' from an HTTPS or SSH GitHub remote URL."""
    cleaned = remote_url.strip()
    patterns = (
        r"github\.com[:/](?P<owner>[^/\s]+)/(?P<repo>[^/\s]+?)(?:\.git)?/?$",
    )
    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if match:
            return f"{match.group('owner')}/{match.group('repo')}"
    return None


def detect_github_repo(cwd: Optional[str] = None) -> str:
    """Detects 'owner/repo' from git origin remote, falling back to DEFAULT_REPO."""
    try:
        completed = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            parsed = parse_github_repo_from_remote(completed.stdout)
            if parsed:
                return parsed
    except (OSError, subprocess.SubprocessError):
        pass
    return DEFAULT_REPO


def resolve_token(explicit_token: Optional[str] = None) -> Optional[str]:
    """Resolves a GitHub API token from CLI argument or environment variables."""
    if explicit_token:
        return explicit_token.strip() or None
    for env_var in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(env_var, "").strip()
        if value:
            return value
    return None


def _build_headers(token: Optional[str]) -> Dict[str, str]:
    headers: Dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "cernodata-fetch-tasks",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _parse_next_link(link_header: Optional[str]) -> Optional[str]:
    """Parses the RFC 5988 Link header and returns the 'next' URL if present."""
    if not link_header:
        return None
    for part in link_header.split(","):
        section = part.strip()
        if 'rel="next"' in section:
            match = re.search(r"<([^>]+)>", section)
            if match:
                return match.group(1)
    return None


def _http_get_json(
    url: str,
    token: Optional[str] = None,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
) -> Tuple[Any, Optional[str]]:
    """Performs a GET request to GitHub API and returns (parsed_json, next_url)."""
    req = urllib.request.Request(url, headers=_build_headers(token), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            next_url = _parse_next_link(resp.headers.get("Link"))
            return json.loads(raw), next_url
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            err_payload = json.loads(exc.read().decode("utf-8", errors="replace"))
            if isinstance(err_payload, dict) and err_payload.get("message"):
                detail = f": {err_payload['message']}"
        except Exception:
            pass
        raise RuntimeError(f"GitHub API HTTP {exc.code} for {url}{detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error contacting GitHub API ({url}): {exc.reason}") from exc


def _issue_from_payload(item: Dict[str, Any]) -> TaskIssue:
    raw_labels = item.get("labels") or []
    labels: List[str] = []
    for lbl in raw_labels:
        if isinstance(lbl, dict) and lbl.get("name"):
            labels.append(str(lbl["name"]))
        elif isinstance(lbl, str):
            labels.append(lbl)

    raw_assignees = item.get("assignees") or []
    assignees: List[str] = [
        str(a["login"]) for a in raw_assignees if isinstance(a, dict) and a.get("login")
    ]

    return TaskIssue(
        number=int(item["number"]),
        title=str(item.get("title") or ""),
        state=str(item.get("state") or ""),
        url=str(item.get("html_url") or ""),
        body=str(item.get("body") or ""),
        labels=tuple(labels),
        assignees=tuple(assignees),
        created_at=str(item.get("created_at") or ""),
        updated_at=str(item.get("updated_at") or ""),
    )


def fetch_issue(
    repo: str,
    issue_number: int,
    token: Optional[str] = None,
    api_base: str = GITHUB_API_BASE,
) -> TaskIssue:
    """Fetches a single GitHub issue by number."""
    url = f"{api_base.rstrip('/')}/repos/{repo}/issues/{issue_number}"
    payload, _ = _http_get_json(url, token=token)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected response payload for issue #{issue_number}.")
    if "pull_request" in payload:
        raise RuntimeError(f"#{issue_number} is a pull request, not an issue.")
    return _issue_from_payload(payload)


def fetch_issues(
    repo: str,
    state: str = "open",
    labels: Optional[Sequence[str]] = None,
    token: Optional[str] = None,
    api_base: str = GITHUB_API_BASE,
    per_page: int = DEFAULT_PER_PAGE,
) -> List[TaskIssue]:
    """Fetches all matching GitHub issues (excluding pull requests) across all pages."""
    params: Dict[str, str] = {
        "state": state,
        "per_page": str(per_page),
        "sort": "created",
        "direction": "asc",
    }
    if labels:
        cleaned_labels = [lbl.strip() for lbl in labels if lbl.strip()]
        if cleaned_labels:
            params["labels"] = ",".join(cleaned_labels)

    query = urllib.parse.urlencode(params)
    next_url: Optional[str] = f"{api_base.rstrip('/')}/repos/{repo}/issues?{query}"
    issues: List[TaskIssue] = []

    while next_url:
        payload, next_url = _http_get_json(next_url, token=token)
        if not isinstance(payload, list):
            raise RuntimeError("Unexpected non-list response from GitHub issues endpoint.")
        for item in payload:
            if not isinstance(item, dict) or "pull_request" in item:
                continue
            issues.append(_issue_from_payload(item))

    return issues


def slugify_title(title: str, max_length: int = 60) -> str:
    """Converts an issue title into a safe lowercase filename slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower()).strip("-")
    if not slug:
        return "issue"
    return slug[:max_length].rstrip("-") or "issue"


def format_issue_markdown(issue: TaskIssue) -> str:
    """Formats a single TaskIssue as a standalone Markdown document."""
    lines: List[str] = [
        f"# #{issue.number}: {issue.title}",
        "",
        f"- **State**: {issue.state}",
        f"- **URL**: {issue.url}",
        f"- **Labels**: {', '.join(issue.labels) if issue.labels else 'None'}",
        f"- **Assignees**: {', '.join(issue.assignees) if issue.assignees else 'Unassigned'}",
        f"- **Created**: {issue.created_at}",
        f"- **Updated**: {issue.updated_at}",
        "",
        "## Description",
        "",
        issue.body.strip() if issue.body.strip() else "_No description provided._",
        "",
    ]
    return "\n".join(lines)


def format_issues_text(issues: Sequence[TaskIssue], include_body: bool = False) -> str:
    """Formats a list of TaskIssues for concise terminal display."""
    if not issues:
        return "No matching GitHub issues found."
    lines: List[str] = []
    for issue in issues:
        label_str = f" [{', '.join(issue.labels)}]" if issue.labels else ""
        lines.append(f"#{issue.number} ({issue.state}){label_str}: {issue.title}")
        lines.append(f"  {issue.url}")
        if include_body and issue.body.strip():
            for body_line in issue.body.strip().splitlines():
                lines.append(f"  | {body_line}")
    return "\n".join(lines)


def export_issues_markdown(issues: Sequence[TaskIssue], output_dir: Path) -> List[Path]:
    """Writes each TaskIssue as a Markdown file under output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for issue in issues:
        filename = f"{issue.number:04d}-{slugify_title(issue.title)}.md"
        target = output_dir / filename
        target.write_text(format_issue_markdown(issue), encoding="utf-8")
        written.append(target)
    return written


def build_parser() -> argparse.ArgumentParser:
    """Constructs the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Fetch project tasks stored as GitHub issues.",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help=f"GitHub repository in 'owner/repo' format (default: auto-detect or {DEFAULT_REPO}).",
    )
    parser.add_argument(
        "--state",
        choices=("open", "closed", "all"),
        default="open",
        help="Filter issues by state (default: open).",
    )
    parser.add_argument(
        "--labels",
        type=str,
        default=None,
        help="Comma-separated list of label names to filter by.",
    )
    parser.add_argument(
        "--issue",
        type=int,
        default=None,
        help="Fetch a single issue by number instead of listing all issues.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "markdown", "json"),
        default="text",
        help="Output format when printing to stdout (default: text).",
    )
    parser.add_argument(
        "--include-body",
        action="store_true",
        help="Include full issue bodies in text output.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to save fetched issues as Markdown files (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print issues to stdout instead of saving them to --output-dir.",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="GitHub personal access token (defaults to GITHUB_TOKEN or GH_TOKEN env var).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entrypoint for fetching GitHub task issues."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    args = build_parser().parse_args(argv)
    repo = args.repo or detect_github_repo()
    token = resolve_token(args.token)
    label_list = [s.strip() for s in args.labels.split(",") if s.strip()] if args.labels else None

    try:
        if args.issue is not None:
            issues = [fetch_issue(repo=repo, issue_number=args.issue, token=token)]
        else:
            issues = fetch_issues(repo=repo, state=args.state, labels=label_list, token=token)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not args.stdout:
        written = export_issues_markdown(issues, Path(args.output_dir))
        print(f"Saved {len(written)} issue(s) from {repo} to {args.output_dir}.")
        return 0

    if args.format == "json":
        print(json.dumps([asdict(item) for item in issues], indent=2))
    elif args.format == "markdown":
        if not issues:
            print("No matching GitHub issues found.")
        else:
            print("\n---\n\n".join(format_issue_markdown(item) for item in issues))
    else:
        show_body = args.include_body or (args.issue is not None)
        print(format_issues_text(issues, include_body=show_body))

    return 0


__all__ = [
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_REPO",
    "GITHUB_API_BASE",
    "TaskIssue",
    "build_parser",
    "detect_github_repo",
    "export_issues_markdown",
    "fetch_issue",
    "fetch_issues",
    "format_issue_markdown",
    "format_issues_text",
    "main",
    "parse_github_repo_from_remote",
    "resolve_token",
    "slugify_title",
]


if __name__ == "__main__":
    sys.exit(main())
