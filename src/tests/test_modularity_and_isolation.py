"""
src/tests/test_modularity_and_isolation.py

Unit tests verifying architectural modularity, isolation, and extensibility improvements:
1. Dynamic options forwarding in PlannerCriteria, DocumentPlan, and IngestionConfig.
2. Declarative HTTP API Router dispatch without modifying handler.py.
3. Extensible ArtifactRegistry export and load hooks without modifying artifact_exporter.py.
4. Pluggable VerificationLayerHandler registration without modifying evaluator.py or violations.py.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.pipeline.artifact_registry import ArtifactDescriptor, ArtifactRegistry
from src.pipeline.config_resolver import PipelineConfigResolver
from src.pipeline.planner import DocumentPlan, PlannerCriteria
from src.pipeline.server.artifacts import RunArtifacts
from src.pipeline.server.router import ApiRouter
from src.quality.registry import (
    QualityRegistry,
    VerificationLayerHandler,
)


class TestModularityAndIsolation(unittest.TestCase):
    """Test suite ensuring loose coupling and isolated extensibility across subsystems."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_modularity_")

    def tearDown(self) -> None:
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_extensible_options_in_criteria_and_plan(self) -> None:
        """Verifies custom options pass through PlannerCriteria to DocumentPlan and IngestionConfig."""
        criteria = PlannerCriteria.from_dict({
            "taxonomy": "general_text",
            "target": "high_precision_structure",
            "security": "air_gapped_local",
            "custom_ocr_dpi": 300,
            "strip_watermarks": True,
        })
        self.assertEqual(criteria.get("custom_ocr_dpi"), 300)
        self.assertTrue(criteria.get("strip_watermarks"))

        plan = DocumentPlan(
            document_path="test.pdf",
            criteria=criteria,
            options={"custom_ocr_dpi": 300, "strip_watermarks": True},
        )
        self.assertEqual(plan.get_option("custom_ocr_dpi"), 300)

        # Automatically forwards to IngestionConfig without parameter changes
        config = plan.to_ingestion_config(output_dir=self.test_dir)
        self.assertEqual(config.get_option("custom_ocr_dpi"), 300)
        self.assertTrue(config.get_option("strip_watermarks"))
        self.assertEqual(config["custom_ocr_dpi"], 300)

        # Serializes round-trip
        plan_dict = plan.to_dict()
        self.assertEqual(plan_dict.get("custom_ocr_dpi"), 300)
        rehydrated = DocumentPlan.from_dict(plan_dict)
        self.assertEqual(rehydrated.get_option("custom_ocr_dpi"), 300)

    def test_config_resolver_absorbs_arbitrary_extra_options(self) -> None:
        """Verifies PipelineConfigResolver absorbs arbitrary extra options into IngestionConfig."""
        _, cfg, _ = PipelineConfigResolver.resolve_request(
            pdf_path="test.pdf",
            target_threshold=0.85,
            experimental_feature=True,
            max_parallel_slices=4,
        )
        self.assertTrue(cfg.get_option("experimental_feature"))
        self.assertEqual(cfg.get_option("max_parallel_slices"), 4)

    def test_declarative_api_router_dispatch(self) -> None:
        """Verifies ApiRouter handles route registration and dispatch without handler switch edits."""
        router = ApiRouter()
        received_post: Dict[str, Any] = {}
        received_get: Dict[str, Any] = {}

        @router.post("/api/custom_action", "/api/alias_action")
        def _handle_custom(handler: Any, payload: Dict[str, Any]) -> None:
            received_post.update(payload)

        @router.get("/api/custom_status")
        def _handle_get(handler: Any, query: Dict[str, List[str]]) -> None:
            received_get.update(query)

        mock_handler = MagicMock()

        # 1. Dispatch POST
        handled_post = router.dispatch_post(mock_handler, "/api/custom_action", {"key": "val123"})
        self.assertTrue(handled_post)
        self.assertEqual(received_post.get("key"), "val123")

        # 2. Dispatch alias POST
        handled_alias = router.dispatch_post(mock_handler, "/api/alias_action", {"alias": True})
        self.assertTrue(handled_alias)
        self.assertTrue(received_post.get("alias"))

        # 3. Dispatch GET
        handled_get = router.dispatch_get(mock_handler, "/api/custom_status", {"filter": ["active"]})
        self.assertTrue(handled_get)
        self.assertEqual(received_get.get("filter"), ["active"])

        # 4. Unknown route returns False
        self.assertFalse(router.dispatch_get(mock_handler, "/api/nonexistent", {}))
        self.assertFalse(router.dispatch_post(mock_handler, "/api/nonexistent", {}))

    def test_extensible_artifact_registry(self) -> None:
        """Verifies custom artifacts can be registered, exported, and loaded without modifying core exporters."""
        registry = ArtifactRegistry()

        def _export_custom(dom: DocumentDOM, dec: Dict[str, Any], viols: List[Dict[str, Any]], out_dir: str, plan: Optional[Dict[str, Any]] = None) -> str:
            out_path = os.path.join(out_dir, "custom_report.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"custom_data": "ok", "total_nodes": len(dom.nodes)}, f)
            return out_path

        def _load_custom(file_path: str) -> Dict[str, Any]:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)

        registry.register(ArtifactDescriptor(
            key="custom_report",
            filename="custom_report.json",
            export_hook=_export_custom,
            load_hook=_load_custom,
        ))

        dom = DocumentDOM(document_id="d1", source_filename="f.pdf", total_pages=1, nodes=[])
        paths = registry.export_artifacts(dom, {}, [], self.test_dir)
        self.assertIn("custom_report", paths)
        self.assertTrue(os.path.exists(paths["custom_report"]))

        loaded = registry.load_artifacts(self.test_dir)
        self.assertIn("custom_report", loaded)
        self.assertEqual(loaded["custom_report"]["custom_data"], "ok")

        # RunArtifacts container integration
        run_artifacts = RunArtifacts(artifacts=loaded)
        self.assertEqual(run_artifacts["custom_report"]["custom_data"], "ok")
        self.assertEqual(run_artifacts.get("custom_report")["custom_data"], "ok")

    def test_custom_verification_layer_handler_registration(self) -> None:
        """Verifies adding a custom verification layer requires only registering a handler class."""
        registry = QualityRegistry()

        class RegexPIILayerHandler(VerificationLayerHandler):
            @property
            def layer_id(self) -> str:
                return "pii_redaction"

            @property
            def level(self) -> int:
                return 6

            @property
            def name(self) -> str:
                return "PII Redaction Invariant"

            @property
            def description(self) -> str:
                return "Flags unredacted sensitive tokens."

            def detect_violations(self, dom: DocumentDOM, counter: int = 1, language: Optional[str] = "en", page_configs: Optional[Dict[int, Any]] = None, fixed_config: Any = None) -> List[Dict[str, Any]]:
                viols: List[Dict[str, Any]] = []
                for n in dom.nodes:
                    text = n.content.get("raw_text", "")
                    if "SECRET" in text:
                        viols.append({
                            "violation_id": f"viol_pii_{counter + len(viols)}",
                            "node_id": n.node_id,
                            "type": "pii_redaction",
                            "rule_type": "unredacted_pii",
                            "severity": "HIGH",
                            "description": "Sensitive keyword detected",
                        })
                return viols

            def evaluate_node(self, node: DOMNode, language: Optional[str] = "en", diacritic_hit: float = 0.20, config: Any = None, suppressed_types: Optional[Dict[str, bool]] = None, garbage_multiplier: float = 3.0) -> float:
                return 0.0 if "SECRET" in node.content.get("raw_text", "") else 1.0

        custom_handler = RegexPIILayerHandler()
        registry.register(custom_handler)

        self.assertIsNotNone(registry.get("pii_redaction"))
        active = registry.get_active(["pii_redaction"])
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].name, "PII Redaction Invariant")

        node_bad = DOMNode(
            node_id="n1", type="paragraph", global_page_index=1, temp_slice_index=1,
            bounding_box=BoundingBox(0.0, 0.0, 10.0, 10.0), content={"raw_text": "Top SECRET"}
        )
        dom = DocumentDOM(document_id="d_pii", source_filename="f.pdf", total_pages=1, nodes=[node_bad])
        viols = custom_handler.detect_violations(dom)
        self.assertEqual(len(viols), 1)
        self.assertEqual(viols[0]["rule_type"], "unredacted_pii")
        self.assertEqual(custom_handler.evaluate_node(node_bad), 0.0)


if __name__ == "__main__":
    unittest.main()
