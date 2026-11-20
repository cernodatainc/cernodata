"""
src/tests/test_pipeline.py

Unit tests for DecisionTreeEngine and end-to-end orchestrator pipeline.
"""

import unittest
from src.pipeline import DecisionTreeEngine, run_pipeline
from src.pipeline.decision_tree import DEFAULT_TARGET_CONFIDENCE_THRESHOLD
from src.tests.conftest import make_test_dom, patch_pipeline_io


class TestPipelineEngine(unittest.TestCase):

    def test_decision_tree_engine_accept(self):
        dom = make_test_dom("High quality text")
        engine = DecisionTreeEngine(target_threshold=0.82)
        res = engine.evaluate(dom)
        self.assertEqual(res["status"], "ACCEPT")
        self.assertTrue(res["is_accepted"])

    def test_decision_tree_engine_fallback(self):
        dom = make_test_dom("Sprawdź termin wykupu w piqtku.")
        engine = DecisionTreeEngine(target_threshold=0.90, language="pl")
        res = engine.evaluate(dom)
        self.assertEqual(res["status"], "TRIGGER_FALLBACK")
        self.assertIn("ocr_language_hint", res["decision_tree"]["recommended_parameter_adjustments"])

    def test_diacritic_hit_triggers_fallback(self):
        dom = make_test_dom("Infolinia w piqtku.")
        engine = DecisionTreeEngine(target_threshold=0.82, language="pl")
        res = engine.evaluate(dom)
        self.assertEqual(res["status"], "TRIGGER_FALLBACK")
        self.assertFalse(res["is_accepted"])
        self.assertLess(res["overall_confidence"], 0.82)

    def test_attempts_history_structure(self):
        dom_bad = make_test_dom("piqtku w piqtku", document_id="doc_bad", source_filename="test.pdf")
        dom_good = make_test_dom("piątku w piątku", document_id="doc_good", source_filename="test.pdf")

        with patch_pipeline_io(parse_side_effect=[dom_bad, dom_good]):
            res = run_pipeline(
                pdf_path="test.pdf",
                target_threshold=DEFAULT_TARGET_CONFIDENCE_THRESHOLD,
                language="pl",
                preset="docling_fast",
                align_skew=True,
                visualize=True,
                output_dir="test_output",
            )
            decision = res["decision"]
            self.assertIn("attempts", decision)
            attempts = decision["attempts"]
            self.assertEqual(len(attempts), 2)
            self.assertEqual(attempts[0]["step"], 1)
            self.assertEqual(attempts[0]["preset"], "docling_fast")
            self.assertEqual(attempts[0]["status"], "TRIGGER_FALLBACK")
            self.assertEqual(attempts[1]["step"], 2)
            self.assertEqual(attempts[1]["preset"], "docling_deep")
            self.assertEqual(attempts[1]["status"], "ACCEPT")
            self.assertIn("detail", attempts[1])

    def test_orchestrator_progress_callback_during_fallback(self):
        dom_bad = make_test_dom("piqtku w piqtku", document_id="doc_bad", source_filename="test.pdf")
        dom_good = make_test_dom("piątku w piątku", document_id="doc_good", source_filename="test.pdf")

        events = []
        def progress_cb(pct: int, step_desc: str, log_msg: str) -> None:
            events.append((pct, step_desc, log_msg))

        with patch_pipeline_io(parse_side_effect=[dom_bad, dom_good]):
            _ = run_pipeline(
                pdf_path="test.pdf",
                language="pl",
                preset="docling_fast",
                target_threshold=0.85,
                align_skew=True,
                visualize=True,
                output_dir="test_output",
                progress_callback=progress_cb,
            )

        step_descriptions = [e[1] for e in events]
        self.assertIn("running docling_fast", step_descriptions)
        fallback_msgs = [desc for desc in step_descriptions if "confidence too low" in desc]
        self.assertTrue(len(fallback_msgs) > 0)
        self.assertIn("starting docling_deep", fallback_msgs[0])
        self.assertIn("running docling_deep", step_descriptions)

    def test_decision_tree_engine_custom_next_preset_id(self):
        dom = make_test_dom("Sprawdź termin wykupu w piqtku.")
        engine = DecisionTreeEngine(
            target_threshold=0.90,
            language="pl",
            next_preset_id="custom_ocr_preset",
        )
        res = engine.evaluate(dom)
        self.assertEqual(res["status"], "TRIGGER_FALLBACK")
        self.assertEqual(res["decision_tree"]["next_preset_candidate"], "custom_ocr_preset")
        self.assertIn("custom_ocr_preset", res["decision_tree"]["reason"])

    def test_decision_tree_engine_custom_wiggle_threshold_and_parameters(self):
        dom = make_test_dom("Sprawdź termin wykupu w piqtku.")
        custom_wiggles = {"custom_filter": "high_pass", "contrast_enhancement": 2.5}
        engine = DecisionTreeEngine(
            target_threshold=0.90,
            current_preset_score=0.95,
            next_preset_score=0.90,
            language="pl",
            wiggle_delta_threshold=0.04,
            wiggle_parameters=custom_wiggles,
        )
        res = engine.evaluate(dom)
        self.assertEqual(res["status"], "TRIGGER_FALLBACK")
        self.assertEqual(res["decision_tree"]["action"], "PATH_B_WIGGLE_PARAMETERS")
        adjustments = res["decision_tree"]["recommended_parameter_adjustments"]
        self.assertEqual(adjustments["custom_filter"], "high_pass")
        self.assertEqual(adjustments["contrast_enhancement"], 2.5)

    def test_fallback_handler_custom_wiggle_scale(self):
        from src.pipeline.fallback_handler import FallbackLoopHandler
        from src.pipeline.planner.models import IngestionConfig

        handler = FallbackLoopHandler()
        cfg = IngestionConfig(preset="docling_fast", options={"wiggle_scale": 5.0})
        scale, force_ocr = handler._resolve_wiggle_parameters(cfg)
        self.assertEqual(scale, 5.0)
        self.assertTrue(force_ocr)

    def test_deprecated_per_run_viewer_export_skipped_by_default(self):
        import warnings
        from unittest.mock import patch
        from src.pipeline.artifact_exporter import export_interactive_html_viewer
        from src.pipeline.artifact_pipeline import PipelineArtifactPipeline
        from src.pipeline.planner.models import IngestionConfig

        dom = make_test_dom("Clean document body", document_id="doc_714", source_filename="doc.pdf")
        decision = {"overall_confidence": 0.95, "status": "ACCEPT", "chosen_preset": "docling_fast"}
        cfg_default = IngestionConfig(output_dir="test_output", visualize=False)

        with patch("src.pipeline.artifact_pipeline.render_visual_overlays", return_value=[]), \
             patch("src.pipeline.artifact_pipeline.export_pipeline_artifacts", return_value=("d.json", "v.json", None)), \
             patch("src.pipeline.artifact_pipeline.export_interactive_html_viewer") as mock_export_viewer:
            res = PipelineArtifactPipeline().export_and_package(
                "doc.pdf", dom, decision, [], cfg_default
            )
            self.assertIsNone(res["html_viewer_path"])
            mock_export_viewer.assert_not_called()

        with patch("src.pipeline.artifact_exporter.generate_interactive_html", return_value="test_output/interactive_viewer.html"):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                out = export_interactive_html_viewer("doc.pdf", dom, decision, [], "test_output")
            self.assertEqual(out, "test_output/interactive_viewer.html")
            self.assertTrue(any(issubclass(w.category, DeprecationWarning) for w in caught))

    def test_attempt_runner_reuses_cached_dom_unless_wiggled(self):
        from src.pipeline.attempt_runner import AttemptRunner
        from src.pipeline.planner.models import IngestionConfig

        cached_dom = make_test_dom("piqtku w piqtku", document_id="doc_cached", source_filename="test.pdf")
        parse_calls = []

        def fake_parse(pdf_path, config=None):
            parse_calls.append(config.preset if config else None)
            return make_test_dom("piątku w piątku", document_id="doc_reparsed", source_filename="test.pdf")

        runner = AttemptRunner(
            parse_fn=fake_parse,
            align_fn=lambda dom, pdf_path, align_skew: dom,
            postprocess_fn=lambda dom, config, pdf_path: dom,
        )

        # Non-wiggled attempt should reuse cached DOM and skip parse_fn
        cfg_normal = IngestionConfig(
            preset="docling_deep",
            target_threshold=0.90,
            language="pl",
            options={"cached_dom_lookup": lambda p: cached_dom if p == "docling_deep" else None},
        )
        dom1, dec1, _ = runner.execute_attempt("test.pdf", cfg_normal, 0.90, 0.72)
        self.assertEqual(parse_calls, [])
        self.assertEqual(dom1.document_id, "doc_cached")
        self.assertFalse(dec1["is_accepted"])

        # Wiggled attempt (force_full_page_ocr=True) must NOT reuse cached DOM
        cfg_wiggled = IngestionConfig(
            preset="docling_deep",
            target_threshold=0.90,
            language="pl",
            force_full_page_ocr=True,
            options={"cached_dom_lookup": lambda p: cached_dom if p == "docling_deep" else None},
        )
        dom2, dec2, _ = runner.execute_attempt("test.pdf", cfg_wiggled, 0.90, 0.72)
        self.assertEqual(parse_calls, ["docling_deep"])
        self.assertEqual(dom2.document_id, "doc_reparsed")
        self.assertTrue(dec2["is_accepted"])

    def test_orchestrator_skips_reparse_when_cached_dom_below_raised_threshold(self):
        from src.pipeline.planner.models import DocumentPlan, PlannerCriteria

        dom_deep_cached = make_test_dom("piqtku w piqtku", document_id="doc_deep", source_filename="test.pdf")
        dom_fallback = make_test_dom("piątku w piątku", document_id="doc_fb", source_filename="test.pdf")

        plan = DocumentPlan(
            document_path="test.pdf",
            criteria=PlannerCriteria(),
            language="pl",
            target_threshold=0.90,
            primary_preset="docling_deep",
            preset_order=["docling_deep", "docling_fast"],
            fallback_queue=[{"preset": "docling_fast", "score": 0.75}],
            scores={"docling_deep": 0.88, "docling_fast": 0.75},
        )

        # Only 1 parse_side_effect needed (for docling_fast fallback), because docling_deep uses cached_dom_lookup
        with patch_pipeline_io(parse_side_effect=[dom_fallback]):
            res = run_pipeline(
                pdf_path="test.pdf",
                target_threshold=0.90,
                language="pl",
                preset="docling_deep",
                align_skew=False,
                visualize=False,
                output_dir="test_output",
                plan=plan,
                cached_dom_lookup=lambda p: dom_deep_cached if p == "docling_deep" else None,
            )
            attempts = res["decision"]["attempts"]
            self.assertEqual(len(attempts), 2)
            self.assertEqual(attempts[0]["preset"], "docling_deep")
            self.assertFalse(attempts[0]["is_accepted"])
            self.assertEqual(attempts[1]["preset"], "docling_fast")
            self.assertTrue(attempts[1]["is_accepted"])

    def test_fallback_skips_failing_preset_and_keeps_best_result(self):
        from src.pipeline.planner.models import DocumentPlan, PlannerCriteria

        dom_deep = make_test_dom("piqtku w piqtku", document_id="doc_deep", source_filename="test.pdf")
        dom_worse = make_test_dom("piqtku piqtku piqtku piqtku", document_id="doc_worse", source_filename="test.pdf")

        plan = DocumentPlan(
            document_path="test.pdf",
            criteria=PlannerCriteria(),
            language="pl",
            target_threshold=0.95,
            primary_preset="docling_deep",
            preset_order=["docling_deep", "pypdfium_rapidocr", "paddleocr_cjk_http"],
            fallback_queue=[
                {"preset": "pypdfium_rapidocr", "score": 0.75},
                {"preset": "paddleocr_cjk_http", "score": 0.70},
            ],
            scores={"docling_deep": 0.88, "pypdfium_rapidocr": 0.75, "paddleocr_cjk_http": 0.70},
        )

        with patch_pipeline_io(
            parse_side_effect=[dom_deep, dom_worse, RuntimeError("HTTP connection refused")]
        ):
            res = run_pipeline(
                pdf_path="test.pdf",
                target_threshold=0.95,
                language="pl",
                preset="docling_deep",
                align_skew=False,
                visualize=False,
                output_dir="test_output",
                plan=plan,
            )

        decision = res["decision"]
        self.assertEqual(decision["chosen_preset"], "docling_deep")
        attempts = decision["attempts"]
        self.assertEqual(len(attempts), 3)
        self.assertEqual(attempts[2]["preset"], "paddleocr_cjk_http")
        self.assertEqual(attempts[2]["status"], "ERROR")


if __name__ == "__main__":
    unittest.main()
