"""
src/tests/test_run_mappings.py

Unit tests for input files and parsing runs mapping repository and API.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from src.pipeline.server.run_mappings import (
    derive_file_set,
    get_file_run_mappings,
    load_persistent_mappings,
    normalize_path,
    record_run_mapping,
)


class TestRunMappings(unittest.TestCase):
    """Validates persistent run mapping indexing, file set grouping, and discovery."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_normalize_and_derive_file_set(self) -> None:
        self.assertEqual(normalize_path("src\\e2e\\Document 8.pdf"), "src/e2e/Document 8.pdf")
        self.assertEqual(derive_file_set("src/e2e/Document 8.pdf"), "e2e")
        self.assertEqual(derive_file_set("data/financial_reports/q3.pdf"), "financial_reports")
        self.assertEqual(derive_file_set("sample.pdf"), "workspace")

    def test_record_and_load_mappings(self) -> None:
        record_run_mapping(
            document_path="src/e2e/Document 8.pdf",
            run_id="output",
            output_dir="output",
            preset="docling_fast",
            status="ACCEPT",
            confidence=0.952,
            violations_count=0,
            total_pages=2,
            timestamp="12:00:00",
            repo_root=self.test_dir,
        )

        mappings = load_persistent_mappings(self.test_dir)
        self.assertIn("src/e2e/Document 8.pdf", mappings)
        doc = mappings["src/e2e/Document 8.pdf"]
        self.assertEqual(doc["file_name"], "Document 8.pdf")
        self.assertEqual(doc["file_set"], "e2e")
        self.assertEqual(len(doc["runs"]), 1)
        self.assertEqual(doc["runs"][0]["run_id"], "output")
        self.assertEqual(doc["runs"][0]["overall_confidence"], 0.952)

        # Update same run id with new status
        record_run_mapping(
            document_path="src/e2e/Document 8.pdf",
            run_id="output",
            output_dir="output",
            preset="docling_fast",
            status="ACCEPT",
            confidence=0.985,
            violations_count=0,
            total_pages=2,
            timestamp="12:05:00",
            repo_root=self.test_dir,
        )
        mappings = load_persistent_mappings(self.test_dir)
        self.assertEqual(len(mappings["src/e2e/Document 8.pdf"]["runs"]), 1)
        self.assertEqual(mappings["src/e2e/Document 8.pdf"]["runs"][0]["overall_confidence"], 0.985)

    def test_get_file_run_mappings_structure(self) -> None:
        # Create mock input files
        e2e_dir = os.path.join(self.test_dir, "src", "e2e")
        os.makedirs(e2e_dir, exist_ok=True)
        pdf1 = os.path.join(e2e_dir, "doc1.pdf")
        with open(pdf1, "wb") as f:
            f.write(b"%PDF-1.4 mock")

        # Create mock run directory
        run_dir = os.path.join(self.test_dir, "output")
        os.makedirs(run_dir, exist_ok=True)
        with open(os.path.join(run_dir, "document_dom.json"), "w", encoding="utf-8") as f:
            json.dump({
                "document_id": "d1",
                "source_filename": "doc1.pdf",
                "total_pages": 1,
                "nodes": [],
            }, f)
        with open(os.path.join(run_dir, "decision_tree.json"), "w", encoding="utf-8") as f:
            json.dump({
                "chosen_preset": "docling_fast",
                "status": "ACCEPT",
                "overall_confidence": 0.95,
                "per_page_confidence": {"1": 0.95},
                "decision_log": ["Preset selected"],
            }, f)
        with open(os.path.join(run_dir, "plan_execution_result.json"), "w", encoding="utf-8") as f:
            json.dump({
                "document_path": "src/e2e/doc1.pdf",
                "chosen_preset": "docling_fast",
                "status": "ACCEPT",
                "overall_confidence": 0.95,
                "per_page_confidence": {"1": 0.95},
                "decision": {
                    "chosen_preset": "docling_fast",
                    "status": "ACCEPT",
                    "overall_confidence": 0.95,
                    "per_page_confidence": {"1": 0.95},
                },
                "violations": [],
            }, f)

        res = get_file_run_mappings(self.test_dir)
        self.assertIn("file_sets", res)
        self.assertIn("all_mappings", res)
        self.assertGreaterEqual(res["total_documents"], 1)

        # Check grouping
        f_sets = {s["file_set"]: s for s in res["file_sets"]}
        self.assertIn("e2e", f_sets)
        e2e_set = f_sets["e2e"]
        self.assertEqual(e2e_set["document_count"], 1)
        self.assertEqual(e2e_set["documents"][0]["file_name"], "doc1.pdf")
        self.assertEqual(e2e_set["documents"][0]["runs_count"], 1)
        self.assertEqual(e2e_set["documents"][0]["runs"][0]["preset"], "docling_fast")

    def test_session_get_file_run_mappings(self) -> None:
        from src.pipeline.server.session import ServerSessionContext

        session = ServerSessionContext(repo_root=self.test_dir)
        mappings = session.get_file_run_mappings()
        self.assertIn("file_sets", mappings)
        self.assertIn("all_mappings", mappings)
