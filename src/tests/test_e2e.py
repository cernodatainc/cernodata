"""
src/tests/test_e2e.py

End-to-end (E2E) pipeline tests with autodiscovery of test documents from src/e2e.
"""

from __future__ import annotations

import glob
import json
import os
import unittest
from typing import Any

from src.pipeline.planner import PresetPlanner


class TestE2EPipeline(unittest.TestCase):

    def setUp(self) -> None:
        self.repo_root: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.e2e_dir: str = os.path.join(self.repo_root, "src", "e2e")
        self.discovered_pdfs: list[str] = sorted(glob.glob(os.path.join(self.e2e_dir, "*.pdf")))

    def test_e2e_documents_discovered(self) -> None:
        """Verifies that E2E test documents are discovered in src/e2e."""
        self.assertGreater(len(self.discovered_pdfs), 0, "No PDF documents discovered in src/e2e")
        doc_names = [os.path.basename(p) for p in self.discovered_pdfs]
        self.assertIn("Dokument 5.pdf", doc_names)
        self.assertIn("Document 8.pdf", doc_names)

    def test_plan_generation_for_discovered_documents(self) -> None:
        """Verifies PresetPlanner creates valid plans for all discovered documents in src/e2e."""
        planner = PresetPlanner()
        for pdf_path in self.discovered_pdfs:
            plan = planner.create_plan(
                document_path=pdf_path,
                taxonomy="general_text",
                hardware="low_spec_cpu",
                target="high_precision_structure",
                security="air_gapped_local",
                language="pl",
                target_threshold=0.82
            )
            self.assertEqual(plan.document_path, pdf_path)
            self.assertIsNotNone(plan.primary_preset)
            self.assertGreaterEqual(len(plan.preset_order), 1)

    def test_e2e_artifacts_exist_for_testcases(self) -> None:
        """Verifies that execution artifacts exist for e2e test documents."""
        # Document 8 artifacts in output_document_8
        doc8_output = os.path.join(self.e2e_dir, "output_document_8")
        if os.path.exists(doc8_output):
            for filename in ["plan.json", "document_dom.json", "quality_violations.json", "plan_execution_result.json", "interactive_viewer.html"]:
                file_path = os.path.join(doc8_output, filename)
                self.assertTrue(os.path.exists(file_path), f"Artifact missing: {file_path}")

            with open(os.path.join(doc8_output, "document_dom.json"), "r", encoding="utf-8") as f:
                dom_data: dict[str, Any] = json.load(f)
            self.assertIn("nodes", dom_data)
            self.assertEqual(dom_data.get("total_pages"), 6)

        # Dokument 5 artifacts in output
        doc5_output = os.path.join(self.e2e_dir, "output")
        if os.path.exists(doc5_output):
            for filename in ["plan.json", "document_dom.json", "quality_violations.json", "plan_execution_result.json", "interactive_viewer.html"]:
                file_path = os.path.join(doc5_output, filename)
                self.assertTrue(os.path.exists(file_path), f"Artifact missing: {file_path}")


if __name__ == "__main__":
    unittest.main()
