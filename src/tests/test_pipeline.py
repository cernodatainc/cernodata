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


if __name__ == "__main__":
    unittest.main()
