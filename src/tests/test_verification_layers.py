"""
src/tests/test_verification_layers.py

Unit tests for deciding verification layers during planning or after finishing a run,
and computing violations and confidence scoring in a materialized manner.
"""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from src.dom import BoundingBox
from src.pipeline.decision_tree import DEFAULT_TARGET_CONFIDENCE_THRESHOLD
from src.pipeline.orchestrator import PipelineOrchestrator, run_pipeline
from src.pipeline.planner import DocumentPlan, PlannerCriteria, PresetPlanner
from src.quality.layers import (
    ALL_VERIFICATION_LAYERS,
    DEFAULT_VERIFICATION_LAYERS,
    VerificationLayer,
    normalize_layer_name,
    normalize_layers,
)
from src.quality.materialization import (
    MaterializedVerificationResult,
    materialize_document_verification,
)
from src.quality.violations import detect_quality_violations
from src.quality.evaluator import evaluate_document_confidence, evaluate_page_confidence
from src.tests.conftest import http_post_json, make_test_dom, make_test_node, running_test_server


class TestVerificationLayers(unittest.TestCase):
    """Test suite validating layer selection during planning, post-run reverification, and materialization."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_verif_layers_")

    def tearDown(self) -> None:
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_layer_normalization_and_aliases(self) -> None:
        """Verifies aliases resolve to canonical verification layer values."""
        self.assertEqual(normalize_layer_name("garbage"), VerificationLayer.SYMBOLS.value)
        self.assertEqual(normalize_layer_name("ocr_noise"), VerificationLayer.SYMBOLS.value)
        self.assertEqual(normalize_layer_name("diacritic"), VerificationLayer.DIACRITICS.value)
        self.assertEqual(normalize_layer_name("language"), VerificationLayer.DIACRITICS.value)
        self.assertEqual(normalize_layer_name("table"), VerificationLayer.TABLES.value)
        self.assertEqual(normalize_layer_name("collision"), VerificationLayer.GEOMETRY.value)
        self.assertEqual(normalize_layer_name("hierarchy"), VerificationLayer.STRUCTURE.value)

        normalized = normalize_layers(["garbage", "diacritic", "table", "garbage"])
        self.assertEqual(normalized, ["symbols", "diacritics", "tables"])

        # None defaults to all verification layers
        self.assertEqual(normalize_layers(None), ALL_VERIFICATION_LAYERS)
        self.assertEqual(DEFAULT_VERIFICATION_LAYERS, ALL_VERIFICATION_LAYERS)

    def test_verification_layers_decided_during_planning(self) -> None:
        """Verifies verification layers can be specified in criteria, planner, and execution plans."""
        planner = PresetPlanner()
        plan = planner.create_plan(
            document_path="sample.pdf",
            taxonomy="financial_report",
            verification_layers=["symbols", "tables"],
        )
        self.assertEqual(plan.verification_layers, ["symbols", "tables"])
        self.assertEqual(plan.criteria.verification_layers, ["symbols", "tables"])

        # Plan to IngestionConfig propagation
        config = plan.to_ingestion_config(output_dir=self.test_dir)
        self.assertEqual(config.verification_layers, ["symbols", "tables"])

        # Serialization round-trip
        plan_path = os.path.join(self.test_dir, "plan.json")
        saved_path = plan.save(plan_path)
        self.assertTrue(os.path.exists(saved_path))

        loaded_plan = DocumentPlan.load(saved_path)
        self.assertEqual(loaded_plan.verification_layers, ["symbols", "tables"])
        self.assertEqual(loaded_plan.criteria.verification_layers, ["symbols", "tables"])

    def test_criteria_serialization_with_custom_layers(self) -> None:
        """Verifies PlannerCriteria dictionary serialization retains custom verification layers."""
        crit = PlannerCriteria(
            taxonomy="general_text",
            target="high_precision_structure",
            verification_layers=["geometry", "structure"],
        )
        as_dict = crit.to_dict()
        self.assertEqual(as_dict["verification_layers"], ["geometry", "structure"])

        hydrated = PlannerCriteria.from_dict(as_dict)
        self.assertEqual(hydrated.verification_layers, ["geometry", "structure"])

    def test_violations_filtered_by_selected_layers(self) -> None:
        """Verifies violation detection strictly respects selected verification criteria."""
        dom = make_test_dom(
            "* Oplata w piqtku oc   )  ch h)",
            document_id="doc_multi",
            node_id="n_multi",
        )

        # 1. When only 'symbols' is selected
        symbols_only = detect_quality_violations(dom, language="pl", layers=["symbols"])
        self.assertTrue(all(v["type"] == "symbols" for v in symbols_only))
        self.assertFalse(any(v["type"] == "diacritic" for v in symbols_only))

        # 2. When only 'diacritics' is selected
        diacritics_only = detect_quality_violations(dom, language="pl", layers=["diacritics"])
        self.assertTrue(all(v["type"] == "diacritic" for v in diacritics_only))
        self.assertFalse(any(v["type"] == "symbols" for v in diacritics_only))

        # 3. When both are selected
        both = detect_quality_violations(dom, language="pl", layers=["symbols", "diacritics"])
        types = {v["type"] for v in both}
        self.assertIn("symbols", types)
        self.assertIn("diacritic", types)

    def test_scoring_calculated_based_on_selected_criteria(self) -> None:
        """Verifies confidence scoring penalizes only active verification layers."""
        node_diacritic_only = make_test_node("Sprawdź termin wykupu Möbel w piątku.", node_id="n_diac")

        score_symbols_only = evaluate_page_confidence(
            [node_diacritic_only], language="pl", layers=["symbols"]
        )
        self.assertEqual(score_symbols_only, 1.0)

        score_diacritics_only = evaluate_page_confidence(
            [node_diacritic_only], language="pl", layers=["diacritics"]
        )
        self.assertLess(score_diacritics_only, 1.0)

        dom_diac = make_test_dom(nodes=[node_diacritic_only], document_id="doc_diac", source_filename="diac.pdf")
        metrics = evaluate_document_confidence(dom_diac, language="pl", layers=["diacritics"])
        self.assertIn("diacritics", metrics["selected_layers"])
        self.assertIn("diacritics", metrics["layer_scores"])

    def test_run_pipeline_with_verification_layers(self) -> None:
        """Verifies run_pipeline propagates verification_layers down to artifacts."""
        dummy_dom = make_test_dom("Sample text", document_id="doc_pipe", source_filename="pipe.pdf")
        with patch("src.pipeline.attempt_runner.parse_document", return_value=dummy_dom):
            res = run_pipeline(
                pdf_path="dummy.pdf",
                target_threshold=DEFAULT_TARGET_CONFIDENCE_THRESHOLD,
                language="en",
                preset="docling_fast",
                align_skew=True,
                output_dir=self.test_dir,
                visualize=False,
                verification_layers=["symbols"],
            )
            self.assertIn("decision", res)
            self.assertEqual(res["decision"].get("selected_layers"), ["symbols"])
            verif_file = os.path.join(self.test_dir, "verification_result.json")
            self.assertTrue(os.path.exists(verif_file))

    def test_materialize_verification_persists_artifacts(self) -> None:
        """Verifies materialize_document_verification creates all materialized artifacts."""
        node = make_test_node("Infolinia czynna w piqtku.", node_id="n_mat")
        dom = make_test_dom(nodes=[node], document_id="doc_mat", source_filename="mat.pdf")

        result = materialize_document_verification(
            dom=dom,
            selected_layers=["diacritics"],
            language="pl",
            target_threshold=0.85,
            output_dir=self.test_dir,
            persist=True,
        )

        # Check in-memory result model
        self.assertIsInstance(result, MaterializedVerificationResult)
        self.assertEqual(result.selected_layers, ["diacritics"])
        self.assertEqual(result.total_violations, 1)
        self.assertIn("diacritics", result.layer_scores)
        self.assertEqual(len(node.violations), 1)

        # Check materialized files on disk
        verif_file = os.path.join(self.test_dir, "verification_result.json")
        viol_file = os.path.join(self.test_dir, "quality_violations.json")
        dec_file = os.path.join(self.test_dir, "decision_tree.json")
        dom_file = os.path.join(self.test_dir, "document_dom.json")

        self.assertTrue(os.path.exists(verif_file))
        self.assertTrue(os.path.exists(viol_file))
        self.assertTrue(os.path.exists(dec_file))
        self.assertTrue(os.path.exists(dom_file))

        with open(verif_file, "r", encoding="utf-8") as f:
            verif_data = json.load(f)
        self.assertEqual(verif_data["selected_layers"], ["diacritics"])
        self.assertEqual(verif_data["total_violations"], 1)

        with open(dec_file, "r", encoding="utf-8") as f:
            dec_data = json.load(f)
        self.assertEqual(dec_data["selected_layers"], ["diacritics"])

    def test_post_run_reverification_changes_decision_and_scoring(self) -> None:
        """Verifies deciding verification layers after run completion recalculates scoring."""
        dom = make_test_dom(
            "Firma dostarczy nowe Möbel do biura.",
            document_id="doc_post",
            source_filename="post_run.pdf",
            node_id="n_post",
        )

        # Initial materialization with all layers (diacritic conflict causes score reduction)
        initial_res = materialize_document_verification(
            dom=dom,
            selected_layers=["symbols", "diacritics"],
            language="pl",
            target_threshold=0.85,
            output_dir=self.test_dir,
            persist=True,
        )
        self.assertLess(initial_res.overall_confidence, 1.0)
        self.assertGreater(initial_res.total_violations, 0)

        # Step 2: Post-run decision - switch verification to 'symbols' only
        orchestrator = PipelineOrchestrator()
        updated_res = orchestrator.reverify(
            output_dir=self.test_dir,
            selected_layers=["symbols"],
            language="pl",
            target_threshold=0.85,
        )

        # Recalculated scoring based on selected criteria
        self.assertEqual(updated_res.selected_layers, ["symbols"])
        self.assertEqual(updated_res.overall_confidence, 1.0)
        self.assertEqual(updated_res.total_violations, 0)
        self.assertEqual(updated_res.status, "ACCEPT")

        # Verify disk artifacts reflect the updated materialized view
        with open(os.path.join(self.test_dir, "verification_result.json"), "r", encoding="utf-8") as f:
            saved_verif = json.load(f)
        self.assertEqual(saved_verif["selected_layers"], ["symbols"])
        self.assertEqual(saved_verif["overall_confidence"], 1.0)
        self.assertEqual(saved_verif["total_violations"], 0)

    def test_structural_and_geometry_verification_layers(self) -> None:
        """Verifies Level 3 structural and Level 5 geometry verification layers detect anomalies."""
        empty_heading = make_test_node("   ", node_id="n_empty_heading", node_type="heading")
        zero_area_node = make_test_node(
            "Valid text with degenerate zero-area bounding box",
            node_id="n_zero_area",
            bbox=BoundingBox(10.0, 10.0, 10.0, 10.0),
        )
        dom = make_test_dom(
            nodes=[empty_heading, zero_area_node],
            document_id="doc_struct_geom",
            source_filename="geom.pdf",
        )

        res = materialize_document_verification(
            dom=dom,
            selected_layers=["structure", "geometry"],
            output_dir=self.test_dir,
            persist=False,
        )
        self.assertGreater(res.total_violations, 0)
        rule_types = {v["rule_type"] for v in res.violations}
        self.assertIn("empty_structural_container", rule_types)
        self.assertIn("zero_area_bounding_box", rule_types)

    def test_tables_verification_layer(self) -> None:
        """Verifies Level 4 tables verification layer detects table grid anomalies."""
        table_node = make_test_node(
            "Header 1 | Header 2\nval1",
            node_id="n_table_grid",
            node_type="table_grid",
            extra_content={"cell_alignment_score": 0.45, "rows": [["col1", "col2"], ["only_col1"]]},
        )
        dom = make_test_dom(nodes=[table_node], document_id="doc_table", source_filename="table.pdf")

        res = materialize_document_verification(
            dom=dom,
            selected_layers=["tables"],
            output_dir=self.test_dir,
            persist=False,
        )
        self.assertGreater(res.total_violations, 0)
        rule_types = {v["rule_type"] for v in res.violations}
        self.assertIn("low_cell_alignment", rule_types)
        self.assertIn("table_column_count_mismatch", rule_types)

    def test_server_verify_layers_endpoint(self) -> None:
        """Verifies the /api/verify_layers HTTP route re-evaluates and materializes run artifacts."""
        dom = make_test_dom("Infolinia czynna w piqtku.", document_id="doc_srv", source_filename="srv.pdf", node_id="n_srv")
        dom.save(os.path.join(self.test_dir, "document_dom.json"))

        with running_test_server(output_dir=self.test_dir) as (server, base_url):
            server.session_context.output_dir = self.test_dir
            server.session_context.repo_root = self.test_dir
            status, body = http_post_json(
                f"{base_url}/api/verify_layers",
                {
                    "output_dir": self.test_dir,
                    "verification_layers": ["symbols"],
                    "language": "pl",
                },
            )
            self.assertEqual(status, 200)
            self.assertTrue(body["success"])
            result = body["result"]
            self.assertEqual(result["selected_layers"], ["symbols"])
            self.assertEqual(result["total_violations"], 0)
            self.assertEqual(result["overall_confidence"], 1.0)


if __name__ == "__main__":
    unittest.main()
