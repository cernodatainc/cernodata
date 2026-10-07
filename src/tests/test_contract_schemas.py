"""
src/tests/test_contract_schemas.py

Unit tests verifying Pydantic schema validation across component seams,
ensuring invalid or corrupted artifacts are dropped instead of silently defaulted.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from src.schemas import (
    DocumentDOMSchema,
    DocumentPlanSchema,
    load_validated_run_artifacts,
    parse_violations_payload,
)


class TestContractSchemas(unittest.TestCase):
    """Test suite for contract schema enforcement at component seams."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_plan_schema_validation(self) -> None:
        sample = {
            "document_path": "test.pdf",
            "taxonomy": "general_text",
            "target": "high_precision_structure",
            "security": "air_gapped_local",
            "target_threshold": 0.85,
            "primary_preset": "docling_fast",
            "preset_order": ["docling_fast", "docling_deep"],
        }
        plan = DocumentPlanSchema.model_validate(sample)
        self.assertEqual(plan.document_path, "test.pdf")
        self.assertEqual(plan.target_threshold, 0.85)
        self.assertEqual(plan.primary_preset, "docling_fast")

    def test_dom_schema_validation(self) -> None:
        sample = {
            "document_id": "doc_123",
            "source_filename": "sample.pdf",
            "total_pages": 2,
            "nodes": [
                {
                    "node_id": "node_1",
                    "type": "heading",
                    "global_page_index": 1,
                    "temp_slice_index": 1,
                    "bounding_box": {"x0": 10.0, "y0": 20.0, "x1": 100.0, "y1": 50.0},
                    "content": {"text": "Title"},
                }
            ],
        }
        dom = DocumentDOMSchema.model_validate(sample)
        self.assertEqual(dom.document_id, "doc_123")
        self.assertEqual(dom.total_pages, 2)
        self.assertEqual(len(dom.nodes), 1)
        self.assertEqual(dom.nodes[0].bounding_box.x0, 10.0)

    def test_violations_schema_and_activity(self) -> None:
        raw_list = [
            {
                "violation_id": "v1",
                "global_page_index": 1,
                "node_id": "n1",
                "type": "symbols",
                "rule_type": "garbage",
                "severity": "HIGH",
                "suppressed": "false",
                "accepted": False,
                "is_fixed": False,
            },
            {
                "violation_id": "v2",
                "global_page_index": 1,
                "node_id": "n2",
                "type": "symbols",
                "rule_type": "garbage",
                "severity": "LOW",
                "suppressed": "true",
            },
        ]
        parsed = parse_violations_payload(raw_list)
        self.assertEqual(len(parsed), 2)
        self.assertTrue(parsed[0].is_active())
        self.assertFalse(parsed[1].is_active())

    def test_corrupt_run_is_dropped(self) -> None:
        # Scenario 1: Empty folder has no DOM -> must be dropped (return None)
        self.assertIsNone(load_validated_run_artifacts(self.temp_dir))

        # Scenario 2: Invalid JSON in DOM file -> must be dropped
        dom_file = os.path.join(self.temp_dir, "document_dom.json")
        with open(dom_file, "w", encoding="utf-8") as f:
            f.write("{invalid_json: true")
        self.assertIsNone(load_validated_run_artifacts(self.temp_dir))

        # Scenario 3: Valid DOM but missing decision -> must be dropped
        with open(dom_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "document_id": "d1",
                    "source_filename": "s.pdf",
                    "total_pages": 1,
                    "nodes": [],
                },
                f,
            )
        self.assertIsNone(load_validated_run_artifacts(self.temp_dir))

    def test_valid_run_is_loaded_with_strong_types(self) -> None:
        dom_file = os.path.join(self.temp_dir, "document_dom.json")
        with open(dom_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "document_id": "d1",
                    "source_filename": "s.pdf",
                    "total_pages": 1,
                    "nodes": [],
                },
                f,
            )
        dec_file = os.path.join(self.temp_dir, "decision_tree.json")
        with open(dec_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "preset_id": "docling_fast",
                    "overall_confidence": 0.94,
                    "per_page_confidence": {"1": 0.94},
                    "status": "ACCEPT",
                    "chosen_preset": "docling_fast",
                },
                f,
            )

        run = load_validated_run_artifacts(self.temp_dir)
        self.assertIsNotNone(run)
        assert run is not None
        self.assertEqual(run.dom.document_id, "d1")
        self.assertEqual(run.decision.preset_id, "docling_fast")
        self.assertEqual(run.overall_confidence, 0.94)
        self.assertEqual(run.status, "ACCEPT")
