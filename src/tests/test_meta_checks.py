"""
src/tests/test_meta_checks.py

Unit tests for repository meta-checks:
- File length scanning, longest file surfacing, and threshold enforcement (> 500 lines).
- Inline CSS and inline JS detection, flagging, and justification verification.
- Repository-level meta check validation.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from src.meta_checks import (
    DEFAULT_MAX_LINES,
    DEFAULT_MUTED_CASES,
    DEFAULT_WARN_LINES,
    FileLengthWarning,
    MutedCase,
    check_file_length_warnings,
    check_file_lengths,
    check_inline_css_and_js,
    run_meta_checks,
    surface_longest_files,
)


class TestMetaChecks(unittest.TestCase):

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="meta_checks_test_")

    def tearDown(self) -> None:
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_file(self, rel_path: str, content: str) -> str:
        full_path = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return full_path

    # =========================================================================
    # File Length & Longest Files Surfacing Tests
    # =========================================================================

    def test_scan_and_surface_longest_files(self) -> None:
        self._create_file("short.py", "x = 1\n" * 10)
        self._create_file("medium.py", "x = 2\n" * 50)
        self._create_file("long.py", "x = 3\n" * 120)

        longest, report = surface_longest_files(self.test_dir, top_n=2)
        self.assertEqual(len(longest), 2)
        self.assertEqual(longest[0].rel_path, "long.py")
        self.assertEqual(longest[0].line_count, 120)
        self.assertEqual(longest[1].rel_path, "medium.py")
        self.assertEqual(longest[1].line_count, 50)

        self.assertIn("long.py", report)
        self.assertIn("120 lines", report)

    def test_check_file_lengths_flags_over_threshold(self) -> None:
        self._create_file("under_limit.py", "x = 1\n" * 450)
        self._create_file("over_limit.py", "x = 1\n" * 550)

        longest, violations = check_file_lengths(self.test_dir, max_lines=500)
        self.assertEqual(len(longest), 2)
        self.assertEqual(len(violations), 1)

        viol = violations[0]
        self.assertEqual(viol.file.rel_path, "over_limit.py")
        self.assertEqual(viol.threshold, 500)
        self.assertIn("exceeds threshold of 500 lines (550 lines)", viol.message)

    def test_check_file_lengths_permits_validly_muted_case(self) -> None:
        self._create_file("legacy_module.py", "x = 1\n" * 600)

        valid_mute = [
            MutedCase(
                file_pattern="legacy_module.py",
                violation_type="file_length",
                justification="Legacy monolithic processor pending decomposition into parser pipelines.",
            )
        ]
        _, violations = check_file_lengths(self.test_dir, max_lines=500, muted_cases=valid_mute)
        self.assertEqual(len(violations), 0)

    def test_check_file_lengths_flags_invalidly_muted_case(self) -> None:
        self._create_file("large.py", "x = 1\n" * 520)

        invalid_mutes = [
            MutedCase(
                file_pattern="large.py",
                violation_type="file_length",
                justification="skip",  # Trivial / banned token
            )
        ]
        _, violations = check_file_lengths(self.test_dir, max_lines=500, muted_cases=invalid_mutes)
        self.assertEqual(len(violations), 1)
        self.assertIn("invalid/trivial mute justification", violations[0].message)

    def test_check_file_length_warnings_flags_yellow_range(self) -> None:
        self.assertEqual(DEFAULT_WARN_LINES, 250)
        self._create_file("short_file.py", "x = 1\n" * 100)
        self._create_file("yellow_flag.py", "x = 1\n" * 300)
        self._create_file("over_limit.py", "x = 1\n" * 550)

        warnings = check_file_length_warnings(self.test_dir, warn_lines=250, max_lines=500)
        self.assertEqual(len(warnings), 1)
        self.assertIsInstance(warnings[0], FileLengthWarning)
        self.assertEqual(warnings[0].file.rel_path, "yellow_flag.py")
        self.assertEqual(warnings[0].warn_threshold, 250)
        self.assertEqual(warnings[0].max_threshold, 500)
        self.assertIn("yellow flag: 250-500 lines", warnings[0].message)

    def test_surface_longest_files_shows_flags(self) -> None:
        self._create_file("small.py", "x = 1\n" * 50)
        self._create_file("warning.py", "x = 1\n" * 300)
        self._create_file("critical.py", "x = 1\n" * 550)

        longest, report = surface_longest_files(self.test_dir, top_n=3, warn_lines=250, max_lines=500)
        self.assertEqual(len(longest), 3)
        self.assertIn("[RED FLAG]", report)
        self.assertIn("[YELLOW FLAG]", report)
        self.assertIn("[OK]", report)

    # =========================================================================
    # Inline CSS & Inline JS Checks
    # =========================================================================

    def test_inline_css_style_tag_flagged(self) -> None:
        html = (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<head>\n"
            "  <style>\n"
            "    body { background: #000; color: #fff; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>Hello</body>\n"
            "</html>\n"
        )
        self._create_file("page.html", html)

        violations = check_inline_css_and_js(self.test_dir)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].violation_type, "inline_style_tag")
        self.assertEqual(violations[0].line_number, 4)
        self.assertIn("Inline <style> tag detected", violations[0].message)

    def test_inline_css_style_attribute_flagged(self) -> None:
        html = (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<body>\n"
            '  <div class="box" style="margin-top: 10px;">Content</div>\n'
            "</body>\n"
            "</html>\n"
        )
        self._create_file("styled.html", html)

        violations = check_inline_css_and_js(self.test_dir)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].violation_type, "inline_style_attribute")
        self.assertEqual(violations[0].line_number, 4)

    def test_inline_js_script_tag_flagged(self) -> None:
        html = (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<body>\n"
            "  <script>\n"
            "    console.log('Inline script running');\n"
            "  </script>\n"
            "</body>\n"
            "</html>\n"
        )
        self._create_file("scripted.html", html)

        violations = check_inline_css_and_js(self.test_dir)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].violation_type, "inline_script_tag")
        self.assertEqual(violations[0].line_number, 4)

    def test_external_script_and_external_css_not_flagged(self) -> None:
        html = (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<head>\n"
            '  <link rel="stylesheet" href="/assets/style.css">\n'
            "</head>\n"
            "<body>\n"
            '  <script src="/assets/app.js"></script>\n'
            "</body>\n"
            "</html>\n"
        )
        self._create_file("clean.html", html)

        violations = check_inline_css_and_js(self.test_dir)
        self.assertEqual(len(violations), 0)

    def test_inline_event_handler_flagged_when_enabled(self) -> None:
        html = (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<body>\n"
            '  <button onclick="handleClick()">Click</button>\n'
            "</body>\n"
            "</html>\n"
        )
        self._create_file("button.html", html)

        # By default include_event_handlers is False
        violations_default = check_inline_css_and_js(self.test_dir, include_event_handlers=False)
        self.assertEqual(len(violations_default), 0)

        # When enabled, it flags the event handler
        violations_with_handlers = check_inline_css_and_js(self.test_dir, include_event_handlers=True)
        self.assertEqual(len(violations_with_handlers), 1)
        self.assertEqual(violations_with_handlers[0].violation_type, "inline_event_handler")

    def test_inline_muted_case_with_valid_justification(self) -> None:
        html = (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<head>\n"
            "  <style>h1 { font-size: 24px; }</style>\n"
            "</head>\n"
            "</html>\n"
        )
        self._create_file("export_template.html", html)

        muted = [
            MutedCase(
                file_pattern="export_template.html",
                violation_type="inline_style_tag",
                justification="Standalone export document template requires bundled styling for offline viewing.",
            )
        ]
        violations = check_inline_css_and_js(self.test_dir, muted_cases=muted)
        self.assertEqual(len(violations), 0)

    def test_inline_muted_case_with_invalid_justification_fails(self) -> None:
        html = (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<head>\n"
            "  <style>h1 { font-size: 24px; }</style>\n"
            "</head>\n"
            "</html>\n"
        )
        self._create_file("bad_mute.html", html)

        muted = [
            MutedCase(
                file_pattern="bad_mute.html",
                violation_type="inline_style_tag",
                justification="too short",  # < 15 chars
            )
        ]
        violations = check_inline_css_and_js(self.test_dir, muted_cases=muted)
        self.assertEqual(len(violations), 1)
        self.assertIn("justification is invalid/trivial", violations[0].message)

    def test_in_file_comment_muting_directive(self) -> None:
        # Valid in-file comment
        html_valid = (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<!-- meta:allow-inline-css: Single-file offline report requires inlined theme variables -->\n"
            "<style>:root { --main: #fff; }</style>\n"
            "</html>\n"
        )
        self._create_file("comment_muted.html", html_valid)
        violations = check_inline_css_and_js(self.test_dir)
        self.assertEqual(len(violations), 0)

        # Invalid in-file comment (trivial reason)
        html_invalid = (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<!-- meta:allow-inline-css: temp -->\n"
            "<style>:root { --main: #fff; }</style>\n"
            "</html>\n"
        )
        self._create_file("comment_invalid.html", html_invalid)
        violations = check_inline_css_and_js(self.test_dir)
        self.assertEqual(len(violations), 1)
        self.assertIn("In-file comment mute has invalid/trivial justification", violations[0].message)

    # =========================================================================
    # Repository Meta Verification
    # =========================================================================

    def test_repository_meta_checks(self) -> None:
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        results = run_meta_checks(
            target_dir=repo_root,
            max_lines=DEFAULT_MAX_LINES,
            muted_cases=DEFAULT_MUTED_CASES,
        )

        # Longest files should be surfaced
        longest = results["longest_files"]
        self.assertGreater(len(longest), 0)
        top = longest[0]
        self.assertIn("path", top)
        self.assertIn("lines", top)
        self.assertGreater(top["lines"], 0)

        # All muted entries must have valid justifications and zero unhandled violations
        self.assertEqual(
            results["length_violations"],
            [],
            f"Unmuted file length violations found: {results['length_violations']}",
        )
        self.assertEqual(
            results["inline_violations"],
            [],
            f"Unmuted inline CSS/JS violations found: {results['inline_violations']}",
        )
        self.assertIsInstance(results["yellow_flags"], list)
        self.assertTrue(results["is_passed"])

    def test_planner_silo_and_dependency_graph(self) -> None:
        """Verifies that dependency graph builder generates valid DOT and confirms planner silo."""
        from pathlib import Path
        from src.dependency_graph import (
            build_dependency_graph,
            generate_dot_graph,
            verify_planner_silo,
        )

        repo_root = Path(__file__).resolve().parents[2]
        graph = build_dependency_graph(repo_root)
        self.assertIn("src.pipeline.planner", graph)

        violations = verify_planner_silo(graph)
        self.assertEqual(violations, [], f"Planner silo violations detected: {violations}")

        dot_output = generate_dot_graph(graph)
        self.assertIn("digraph", dot_output)
        self.assertIn("cluster_planner", dot_output)


if __name__ == "__main__":
    unittest.main()

