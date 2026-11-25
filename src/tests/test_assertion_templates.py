"""
src/tests/test_assertion_templates.py

Checks that the domain assertion templates (TASK-108) load as DocumentAssertionSuite.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.schemas.test_suite import DocumentAssertionSuite

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "schemas" / "examples" / "assertion_templates"
RULE_LISTS = ("required_headers", "regex_rules", "table_rules")
MAX_TEMPLATE_LINES = 180


class TestAssertionTemplates(unittest.TestCase):
    """Every template parses, keeps all its rules, and stays documented and short."""

    def test_all_templates_load_without_dropping_rules(self) -> None:
        paths = sorted(TEMPLATES_DIR.glob("*.json"))
        self.assertEqual(len(paths), 5)
        for path in paths:
            with self.subTest(template=path.name):
                raw = json.loads(path.read_text(encoding="utf-8"))
                parsed = DocumentAssertionSuite.from_dict(raw).to_dict()

                self.assertTrue(raw.get("description"))
                self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), MAX_TEMPLATE_LINES)
                self.assertEqual(parsed["min_node_counts"], raw.get("min_node_counts", {}))
                for key in RULE_LISTS:
                    self.assertEqual(len(parsed[key]), len(raw.get(key, [])))
                    for rule in raw.get(key, []):
                        self.assertTrue(rule.get("description"), f"{key} rule without description")


if __name__ == "__main__":
    unittest.main()
