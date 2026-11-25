"""
src/tests/test_ui_test_suite_routes.py

Route tests for the Web Hub output expectations and test questions card (TASK-107).
"""

from __future__ import annotations

import json
from typing import Any

from src.tests.conftest import EphemeralServerTestCase, http_get, http_post_json, make_test_dom, make_test_node

DOM = make_test_dom(
    nodes=[
        make_test_node("Overview", node_id="n1", node_type="heading"),
        make_test_node("Effective Q3, the EU price for the Team tier is 11.90.", node_id="n2"),
        make_test_node("| Tier | EUR |\n|---|---|\n| Team | 12.50 |", node_id="n3", node_type="table_grid",
                       extra_content={"rows": [["Tier", "EUR"], ["Team", "12.50"]]}),
    ],
    source_filename="doc_pricing_matrix.pdf",
)


class TestUiTestSuiteRoutes(EphemeralServerTestCase):
    """GET /api/test_templates and POST /api/test_suite_check against the session's parsed document."""

    def _check(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        return http_post_json(f"{self.base_url}/api/test_suite_check", payload)

    def setUp(self) -> None:
        session = self.server.session_context
        session.current_result = {"dom": DOM.to_dict(), "decision": {}, "violations": []}
        session.pdf_path = "src/e2e/retrieval_benchmark/doc_pricing_matrix.pdf"

    def test_lists_domain_templates(self) -> None:
        status, body, _ = http_get(f"{self.base_url}/api/test_templates")

        self.assertEqual(status, 200)
        self.assertIn("financial_report_or_invoice", json.loads(body)["templates"])

    def test_reports_pass_and_fail_for_every_rule_and_question(self) -> None:
        status, body = self._check({
            "required_headers": ["Overview", "Governing Law"],
            "min_table_columns": 3,
            "questions": [
                {"question": "What is the EU price for the Team tier effective Q3?", "expected_answer": "11.90"},
                {"question": "What is the EU price for the Team tier effective Q3?", "expected_answer": "11.95"},
            ],
        })

        self.assertEqual(status, 200)
        self.assertEqual(body["document"], "doc_pricing_matrix.pdf")
        outcome = [(r["type"], r["passed"]) for r in body["results"]]
        self.assertEqual(outcome, [
            ("header", True), ("header", False), ("table", False), ("question", True), ("question", False),
        ])
        self.assertIn("2 column(s), expected at least 3", body["results"][2]["detail"])
        self.assertEqual(len({r["id"] for r in body["results"]}), 5)

    def test_template_rules_are_included(self) -> None:
        status, body = self._check({"template": "financial_report_or_invoice"})

        self.assertEqual(status, 200)
        self.assertEqual({r["type"] for r in body["results"]}, {"header", "pattern", "table", "node_count"})
        self.assertTrue(all(r["label"] for r in body["results"]))

    def test_rejects_unknown_template_and_missing_run(self) -> None:
        status, body = self._check({"template": "../secrets"})
        self.assertEqual(status, 400)
        self.assertIn("unknown template", body["error"])

        self.server.session_context.current_result = None
        status, body = self._check({"required_headers": ["Overview"]})
        self.assertEqual(status, 400)
        self.assertIn("run the pipeline first", body["error"])
