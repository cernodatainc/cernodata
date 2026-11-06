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
    forget_document,
    get_file_run_mappings,
    load_persistent_mappings,
    normalize_path,
    record_run_mapping,
    register_document_path,
    unforget_document,
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

    def test_remove_run_mapping(self) -> None:
        from src.pipeline.server.run_mappings import remove_run_mapping

        record_run_mapping(
            document_path="src/e2e/doc1.pdf",
            run_id="run_to_delete",
            output_dir="output/run_to_delete",
            preset="docling_fast",
            status="ACCEPT",
            confidence=0.95,
            violations_count=0,
            repo_root=self.test_dir,
        )
        before = get_file_run_mappings(self.test_dir)
        doc_entry = next(d for d in before["all_mappings"] if d["file_name"] == "doc1.pdf")
        self.assertEqual(len(doc_entry["runs"]), 1)

        ok = remove_run_mapping(
            run_id="run_to_delete",
            output_dir="output/run_to_delete",
            repo_root=self.test_dir,
        )
        self.assertTrue(ok)
        after = get_file_run_mappings(self.test_dir)
        doc_entry_after = next(d for d in after["all_mappings"] if d["file_name"] == "doc1.pdf")
        self.assertEqual(len(doc_entry_after["runs"]), 0)
        self.assertEqual(doc_entry_after["runs_count"], 0)
        # Ensure _removed_runs is not treated as an artificial document
        self.assertFalse(any(d["file_name"] == "_removed_runs" for d in after["all_mappings"]))
        self.assertFalse(any(d["file_path"] == "_removed_runs" for d in after["all_mappings"]))

    def test_active_file_and_run_consistency(self) -> None:
        from src.pipeline.server.run_mappings import remove_run_mapping

        # Document 5 with run
        record_run_mapping(
            document_path="src/e2e/Dokument 5.pdf",
            run_id="run_doc_5",
            output_dir="output/run_doc_5",
            preset="docling_fast",
            status="TRIGGER_FALLBACK",
            confidence=0.25,
            violations_count=5,
            repo_root=self.test_dir,
        )
        # Document 8 with run
        record_run_mapping(
            document_path="src/e2e/Document 8.pdf",
            run_id="run_doc_8",
            output_dir="output/run_doc_8",
            preset="docling_fast",
            status="ACCEPT",
            confidence=0.95,
            violations_count=0,
            repo_root=self.test_dir,
        )

        remove_run_mapping(
            run_id="run_doc_5",
            output_dir="output/run_doc_5",
            repo_root=self.test_dir,
        )

        mappings = get_file_run_mappings(self.test_dir)
        # Verify _removed_runs is excluded from documents
        doc_names = [d["file_name"] for d in mappings["all_mappings"]]
        self.assertNotIn("_removed_runs", doc_names)

        # Active file and active run should be consistent with a doc that has runs
        active_doc = mappings["active_file"]
        active_run = mappings["active_run"]
        self.assertIn("Document 8", active_doc)
        self.assertEqual(active_run, "output/run_doc_8")

    def test_remove_run_isolated_to_single_document(self) -> None:
        from src.pipeline.server.run_mappings import remove_run_mapping

        # Both Document 5 and Document 8 have a run sharing "output"
        record_run_mapping(
            document_path="src/e2e/Dokument 5.pdf",
            run_id="output",
            output_dir="output",
            preset="docling_fast",
            status="TRIGGER_FALLBACK",
            confidence=0.30,
            violations_count=4,
            repo_root=self.test_dir,
        )
        record_run_mapping(
            document_path="src/e2e/Document 8.pdf",
            run_id="output",
            output_dir="output",
            preset="docling_fast",
            status="ACCEPT",
            confidence=0.92,
            violations_count=0,
            repo_root=self.test_dir,
        )

        # Remove Document 5's run only
        ok = remove_run_mapping(
            run_id="output",
            output_dir="output",
            document_path="src/e2e/Dokument 5.pdf",
            repo_root=self.test_dir,
        )
        self.assertTrue(ok)

        mappings = get_file_run_mappings(self.test_dir)
        d5_entry = next((d for d in mappings["all_mappings"] if d["file_name"] == "Dokument 5.pdf"), None)
        d8_entry = next((d for d in mappings["all_mappings"] if d["file_name"] == "Document 8.pdf"), None)

        self.assertIsNotNone(d5_entry)
        self.assertIsNotNone(d8_entry)
        # Document 5 run must be removed
        self.assertEqual(len(d5_entry["runs"]), 0)
        # Document 8 run must be PRESERVED
        self.assertEqual(len(d8_entry["runs"]), 1)
        self.assertEqual(d8_entry["runs"][0]["run_id"], "output")

    def test_forget_document_removes_from_explorer_and_preserves_runs(self) -> None:
        # Create mock input file
        e2e_dir = os.path.join(self.test_dir, "src", "e2e")
        os.makedirs(e2e_dir, exist_ok=True)
        pdf_path = os.path.join(e2e_dir, "to_forget.pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"%PDF-1.4 mock")

        # Record run and create physical run artifact
        run_dir = os.path.join(self.test_dir, "output", "run_forget_test")
        os.makedirs(run_dir, exist_ok=True)
        dom_file = os.path.join(run_dir, "document_dom.json")
        with open(dom_file, "w", encoding="utf-8") as f:
            json.dump({"document_id": "d_forget", "source_filename": "to_forget.pdf"}, f)

        record_run_mapping(
            document_path="src/e2e/to_forget.pdf",
            run_id="run_forget_test",
            output_dir="output/run_forget_test",
            preset="docling_fast",
            status="ACCEPT",
            confidence=0.96,
            violations_count=0,
            repo_root=self.test_dir,
        )

        before = get_file_run_mappings(self.test_dir)
        doc_names_before = [d["file_name"] for d in before["all_mappings"]]
        self.assertIn("to_forget.pdf", doc_names_before)

        # Forget the document
        ok = forget_document("src/e2e/to_forget.pdf", repo_root=self.test_dir)
        self.assertTrue(ok)

        after = get_file_run_mappings(self.test_dir)
        doc_names_after = [d["file_name"] for d in after["all_mappings"]]
        self.assertNotIn("to_forget.pdf", doc_names_after)
        self.assertNotIn("_forgotten_files", doc_names_after)
        self.assertEqual(after.get("forgotten_count"), 1)

        # Past runs MUST NOT be deleted
        self.assertTrue(os.path.exists(dom_file), "Past run artifacts on disk must not be deleted when forgetting a file")

    def test_unforget_document_on_register(self) -> None:
        forget_document("src/e2e/temp_doc.pdf", repo_root=self.test_dir)
        mappings = load_persistent_mappings(self.test_dir)
        self.assertIn("src/e2e/temp_doc.pdf", mappings.get("_forgotten_files", []))

        # Test explicit unforget_document
        unforgotten = unforget_document("src/e2e/temp_doc.pdf", repo_root=self.test_dir)
        self.assertTrue(unforgotten)
        mappings_unforgot = load_persistent_mappings(self.test_dir)
        self.assertNotIn("src/e2e/temp_doc.pdf", mappings_unforgot.get("_forgotten_files", []))

        # Re-register document
        forget_document("src/e2e/temp_doc.pdf", repo_root=self.test_dir)
        register_document_path("src/e2e/temp_doc.pdf", repo_root=self.test_dir)
        mappings_after = load_persistent_mappings(self.test_dir)
        self.assertNotIn("src/e2e/temp_doc.pdf", mappings_after.get("_forgotten_files", []))

    def test_session_forget_document(self) -> None:
        from src.pipeline.server.session import ServerSessionContext

        session = ServerSessionContext(repo_root=self.test_dir)
        session.pdf_path = "src/e2e/active_doc.pdf"
        session.register_document("src/e2e/active_doc.pdf")

        self.assertIn("src/e2e/active_doc.pdf", session.get_available_documents())

        ok = session.forget_document("src/e2e/active_doc.pdf")
        self.assertTrue(ok)
        self.assertNotIn("src/e2e/active_doc.pdf", session.get_available_documents())
        self.assertEqual(session.pdf_path, "")

    def test_unforget_when_discovering_file_from_scratch(self) -> None:
        from src.pipeline.server.session import ServerSessionContext

        # Create mock file and run
        e2e_dir = os.path.join(self.test_dir, "src", "e2e")
        os.makedirs(e2e_dir, exist_ok=True)
        doc_file = os.path.join(e2e_dir, "discover_again.pdf")
        with open(doc_file, "wb") as f:
            f.write(b"%PDF-1.4 mock")

        record_run_mapping(
            document_path="src/e2e/discover_again.pdf",
            run_id="run_past_1",
            output_dir="output/run_past_1",
            preset="docling_fast",
            status="ACCEPT",
            confidence=0.97,
            violations_count=0,
            repo_root=self.test_dir,
        )

        session = ServerSessionContext(repo_root=self.test_dir)
        before = session.get_file_run_mappings()
        self.assertTrue(any(d["file_name"] == "discover_again.pdf" for d in before["all_mappings"]))

        # Forget the file
        session.forget_document("src/e2e/discover_again.pdf")
        after_forget = session.get_file_run_mappings()
        self.assertFalse(any(d["file_name"] == "discover_again.pdf" for d in after_forget["all_mappings"]))

        # User attempts to discover the file from scratch
        session.register_document("src/e2e/discover_again.pdf")
        after_discovery = session.get_file_run_mappings()

        # Document is restored along with its historical runs
        doc_entry = next((d for d in after_discovery["all_mappings"] if d["file_name"] == "discover_again.pdf"), None)
        self.assertIsNotNone(doc_entry, "Discovered file should be unforgotten and visible in explorer")
        self.assertEqual(len(doc_entry["runs"]), 1, "Past runs should be intact and restored in explorer")
        self.assertEqual(doc_entry["runs"][0]["run_id"], "run_past_1")


