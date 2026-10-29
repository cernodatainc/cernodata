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

from src.dom import BoundingBox, DOMNode, DocumentDOM
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
        # Node with both garbage text and Polish diacritic anomaly
        node = DOMNode(
            node_id="n_multi",
            type="paragraph",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(10.0, 10.0, 200.0, 50.0),
            content={"raw_text": "* Oplata w piqtku oc   )  ch h)"},
        )
        dom = DocumentDOM(
            document_id="doc_multi",
            source_filename="sample.pdf",
            total_pages=1,
            nodes=[node],
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
        # Node with clean character text but diacritic conflict
        node_diacritic_only = DOMNode(
            node_id="n_diac",
            type="paragraph",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(10.0, 10.0, 200.0, 50.0),
            content={"raw_text": "Sprawdź termin wykupu Möbel w piątku."},
        )

        # In Polish context:
        # Under symbols layer only: text has no garbage, so confidence should be 1.0
        score_symbols_only = evaluate_page_confidence(
            [node_diacritic_only], language="pl", layers=["symbols"]
        )
        self.assertEqual(score_symbols_only, 1.0)

        # Under diacritics layer: 'Möbel' triggers conflict penalty in Polish
        score_diacritics_only = evaluate_page_confidence(
            [node_diacritic_only], language="pl", layers=["diacritics"]
        )
        self.assertLess(score_diacritics_only, 1.0)

        dom_diac = DocumentDOM(
            document_id="doc_diac",
            source_filename="diac.pdf",
            total_pages=1,
            nodes=[node_diacritic_only],
        )
        metrics = evaluate_document_confidence(dom_diac, language="pl", layers=["diacritics"])
        self.assertIn("diacritics", metrics["selected_layers"])
        self.assertIn("diacritics", metrics["layer_scores"])

    def test_run_pipeline_with_verification_layers(self) -> None:
        """Verifies run_pipeline propagates verification_layers down to artifacts."""
        dummy_dom = DocumentDOM(
            document_id="doc_pipe",
            source_filename="pipe.pdf",
            total_pages=1,
            nodes=[
                DOMNode(
                    node_id="n1",
                    type="paragraph",
                    global_page_index=1,
                    temp_slice_index=1,
                    bounding_box=BoundingBox(10.0, 10.0, 100.0, 30.0),
                    content={"raw_text": "Sample text"},
                )
            ],
        )
        with patch("src.pipeline.attempt_runner.parse_document", return_value=dummy_dom):
            res = run_pipeline(
                pdf_path="dummy.pdf",
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
        node = DOMNode(
            node_id="n_mat",
            type="paragraph",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(10.0, 10.0, 150.0, 40.0),
            content={"raw_text": "Infolinia czynna w piqtku."},
        )
        dom = DocumentDOM(
            document_id="doc_mat",
            source_filename="mat.pdf",
            total_pages=1,
            nodes=[node],
        )

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
        # Step 1: Simulate a finished run with a diacritic error
        node = DOMNode(
            node_id="n_post",
            type="paragraph",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(10.0, 10.0, 150.0, 40.0),
            content={"raw_text": "Firma dostarczy nowe Möbel do biura."},
        )
        dom = DocumentDOM(
            document_id="doc_post",
            source_filename="post_run.pdf",
            total_pages=1,
            nodes=[node],
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
        empty_heading = DOMNode(
            node_id="n_empty_heading",
            type="heading",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(10.0, 10.0, 100.0, 30.0),
            content={"raw_text": "   "},
        )
        zero_area_node = DOMNode(
            node_id="n_zero_area",
            type="paragraph",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(10.0, 10.0, 10.0, 10.0),  # width == 0
            content={"raw_text": "Valid text with degenerate zero-area bounding box"},
        )
        dom = DocumentDOM(
            document_id="doc_struct_geom",
            source_filename="geom.pdf",
            total_pages=1,
            nodes=[empty_heading, zero_area_node],
        )

        # When evaluated with structure and geometry layers
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
        table_node = DOMNode(
            node_id="n_table_grid",
            type="table_grid",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(10.0, 10.0, 300.0, 200.0),
            content={
                "raw_text": "Header 1 | Header 2\nval1",
                "cell_alignment_score": 0.45,
                "rows": [["col1", "col2"], ["only_col1"]],
            },
        )
        dom = DocumentDOM(
            document_id="doc_table",
            source_filename="table.pdf",
            total_pages=1,
            nodes=[table_node],
        )

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
        # 1. Setup mock run directory with document_dom.json
        node = DOMNode(
            node_id="n_srv",
            type="paragraph",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(10.0, 10.0, 150.0, 40.0),
            content={"raw_text": "Infolinia czynna w piqtku."},
        )
        dom = DocumentDOM(
            document_id="doc_srv",
            source_filename="srv.pdf",
            total_pages=1,
            nodes=[node],
        )
        dom.save(os.path.join(self.test_dir, "document_dom.json"))

        # 2. Launch lightweight server
        import urllib.request
        from src.pipeline.server import PipelineViewerServer, find_available_port

        port = find_available_port(18890)
        from src.pipeline.server import PipelineViewerHandler
        server = PipelineViewerServer(("127.0.0.1", port), PipelineViewerHandler)
        server.output_dir = self.test_dir
        server.session_context.output_dir = self.test_dir
        server.session_context.repo_root = self.test_dir
        import threading
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()

        try:
            # Send POST /api/verify_layers requesting 'symbols' layer only
            req_data = json.dumps({
                "output_dir": self.test_dir,
                "verification_layers": ["symbols"],
                "language": "pl",
            }).encode("utf-8")
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/verify_layers",
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200)
                body = json.loads(resp.read().decode("utf-8"))

            self.assertTrue(body["success"])
            result = body["result"]
            self.assertEqual(result["selected_layers"], ["symbols"])
            self.assertEqual(result["total_violations"], 0)
            self.assertEqual(result["overall_confidence"], 1.0)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
