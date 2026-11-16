"""
src/tests/test_threshold_cache_replan.py

Integration tests for threshold-aware cache reuse, replanning, and UI submit button reset.
"""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import patch

from src.dom import DocumentDOM
from src.tests.conftest import EphemeralServerTestCase, http_get, http_post_json, make_test_dom


class TestThresholdCacheReplan(EphemeralServerTestCase):
    """Verifies that raising target_threshold bypasses insufficient cached runs and reuses deterministic DOMs."""

    def _get(self, path: str) -> tuple[int, str, Dict[str, str]]:
        return http_get(f"{self.base_url}{path}")

    def _post_json(self, path: str, data: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
        return http_post_json(f"{self.base_url}{path}", data)

    def test_api_run_respects_raised_threshold_and_passes_cached_dom_lookup(self) -> None:
        cached_dom = make_test_dom("Sample text", document_id="doc_deep_cached", source_filename="doc.pdf")
        cached_result = {
            "dom": cached_dom.to_dict(),
            "decision": {
                "chosen_preset": "docling_deep",
                "status": "ACCEPT",
                "overall_confidence": 0.87,
                "per_page_confidence": {"1": 0.87},
                "target_confidence_threshold": 0.85,
            },
            "violations": [],
            "plan": None,
        }
        self.server.session_context._preset_cache.put(
            "src/e2e/Document 8.pdf",
            "docling_deep",
            cached_result,
            language="pl",
        )

        # At threshold 0.85, cached docling_deep (0.87) is sufficient and served directly
        status_ok, resp_ok = self._post_json("/api/run", {
            "pdf_path": "src/e2e/Document 8.pdf",
            "preset": "docling_deep",
            "language": "pl",
            "target_threshold": 0.85,
        })
        self.assertEqual(status_ok, 200)
        self.assertTrue(resp_ok.get("cached"))

        # At threshold 0.90, cached docling_deep (0.87) is insufficient, so run_pipeline runs with cached_dom_lookup
        captured: Dict[str, Any] = {}

        def fake_run_pipeline(**kwargs: Any) -> Dict[str, Any]:
            captured.update(kwargs)
            lookup = kwargs.get("cached_dom_lookup")
            looked_up = lookup("docling_deep") if callable(lookup) else None
            captured["looked_up_dom"] = looked_up
            return {
                "dom": cached_dom.to_dict(),
                "decision": {
                    "chosen_preset": "docling_fast",
                    "status": "ACCEPT",
                    "overall_confidence": 0.93,
                    "per_page_confidence": {"1": 0.93},
                    "target_confidence_threshold": 0.90,
                },
                "violations": [],
                "plan": None,
            }

        with patch("src.pipeline.orchestrator.run_pipeline", side_effect=fake_run_pipeline):
            status_new, resp_new = self._post_json("/api/run", {
                "pdf_path": "src/e2e/Document 8.pdf",
                "preset": "docling_deep",
                "language": "pl",
                "target_threshold": 0.90,
            })

        self.assertEqual(status_new, 200)
        self.assertFalse(resp_new.get("cached", False))
        self.assertIsNotNone(captured.get("cached_dom_lookup"))
        self.assertIsInstance(captured.get("looked_up_dom"), DocumentDOM)
        self.assertEqual(captured["looked_up_dom"].document_id, "doc_deep_cached")
        self.assertEqual(resp_new["decision"]["chosen_preset"], "docling_fast")

    def test_frontend_scripts_include_submit_button_reset_and_threshold_check(self) -> None:
        s1, ds_js, _ = self._get("/data_shape_config.js")
        self.assertEqual(s1, 200)
        self.assertIn("resetSubmitPlanButton", ds_js)
        self.assertIn("meetsThreshold", ds_js)

        s2, l_js, _ = self._get("/landing.js")
        self.assertEqual(s2, 200)
        self.assertIn("resetSubmitPlanButton", l_js)
        self.assertIn("meetsThreshold", l_js)
