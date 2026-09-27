"""
src/tests/test_planner.py

Unit tests for PresetPlanner, DocumentPlan serialization, override behavior,
and plan-driven pipeline execution.
"""

import os
import unittest
from src.pipeline.planner import PresetPlanner, DocumentPlan
from src.pipeline.planner_models import PlannerCriteria, IngestionConfig
from src.pipeline.orchestrator import run_pipeline, parse_document, evaluate_quality_and_decision_tree


class TestPlanner(unittest.TestCase):

    def setUp(self):
        self.planner = PresetPlanner()

    def test_calculate_scores_general_text(self):
        scores = self.planner.calculate_scores(
            taxonomy="general_text",
            target="rapid_approximate",
            security="air_gapped_local"
        )
        self.assertIn("docling_fast", scores)
        self.assertIn("docling_deep", scores)
        self.assertIn("vision_llm_direct", scores)
        self.assertGreater(scores["docling_fast"], scores["vision_llm_direct"])

    def test_calculate_scores_financial_report(self):
        scores = self.planner.calculate_scores(
            taxonomy="financial_report",
            target="high_precision_structure",
            security="air_gapped_local"
        )
        self.assertGreater(scores["docling_deep"], scores["docling_fast"])
        suggested = self.planner.suggest_preset_order(scores)
        self.assertEqual(suggested[0], "docling_deep")

    def test_create_plan_default(self):
        plan = self.planner.create_plan(
            document_path="src/e2e/Dokument 5.pdf",
            taxonomy="financial_report",
            target="high_precision_structure",
            security="air_gapped_local",
            language="pl"
        )
        self.assertFalse(plan.overridden)
        self.assertEqual(plan.primary_preset, "docling_deep")
        self.assertEqual(plan.language, "pl")
        self.assertGreater(len(plan.fallback_queue), 0)

    def test_create_plan_with_override(self):
        plan = self.planner.create_plan(
            document_path="src/e2e/Dokument 5.pdf",
            taxonomy="financial_report",
            target="high_precision_structure",
            security="air_gapped_local",
            override_primary="docling_fast"
        )
        self.assertTrue(plan.overridden)
        self.assertEqual(plan.primary_preset, "docling_fast")
        self.assertIn("docling_deep", [f["preset"] for f in plan.fallback_queue])

    def test_create_plan_with_order_override(self):
        custom_order = ["vision_llm_direct", "docling_fast", "docling_deep"]
        plan = self.planner.create_plan(
            override_order=custom_order
        )
        self.assertTrue(plan.overridden)
        self.assertEqual(plan.preset_order, custom_order)
        self.assertEqual(plan.primary_preset, "vision_llm_direct")

    def test_create_plan_without_language_hint(self):
        plan = self.planner.create_plan(language=None)
        self.assertIsNone(plan.language)
        test_path = "test_output/test_plan_no_lang.json"
        saved_path = plan.save(test_path)
        self.assertTrue(os.path.exists(saved_path))

        loaded = DocumentPlan.load(saved_path)
        self.assertIsNone(loaded.language)
        self.assertEqual(loaded.primary_preset, plan.primary_preset)

        if os.path.exists(test_path):
            os.remove(test_path)

    def test_plan_save_and_load(self):
        plan = self.planner.create_plan(language="de", target_threshold=0.88)
        test_path = "test_output/test_plan.json"
        saved_path = plan.save(test_path)
        self.assertTrue(os.path.exists(saved_path))

        loaded = DocumentPlan.load(saved_path)
        self.assertEqual(loaded.language, "de")
        self.assertEqual(loaded.target_threshold, 0.88)
        self.assertEqual(loaded.primary_preset, plan.primary_preset)

        if os.path.exists(test_path):
            os.remove(test_path)

    def test_interactive_session_mocked(self):
        # Mock user inputs for 5 steps:
        # [1] custom doc path: 'src/e2e/Dokument 5.pdf'
        # [2] choice 1 (financial_report)
        # [3] choice 2 (high_precision_structure)
        # [4] choice 1 (air_gapped_local)
        # [5] lang: 'pl', threshold: '0.85'
        # Override prompt: 'y'
        inputs = ["src/e2e/Dokument 5.pdf", "1", "2", "1", "pl", "0.85", "y"]
        input_gen = iter(inputs)

        def mock_input(prompt=""):
            return next(input_gen)

        messages = []
        def mock_print(*args):
            messages.append(" ".join(str(a) for a in args))

        plan = self.planner.interactive_session(input_func=mock_input, print_func=mock_print)
        self.assertEqual(plan.document_path, "src/e2e/Dokument 5.pdf")
        self.assertEqual(plan.taxonomy, "financial_report")
        self.assertEqual(plan.language, "pl")
        self.assertEqual(plan.target_threshold, 0.85)
        self.assertEqual(plan.primary_preset, "docling_deep")
        self.assertFalse(plan.overridden)

    def test_interactive_session_no_language_hint(self):
        # Empty string for language hint sets language to None
        inputs = ["src/e2e/Dokument 5.pdf", "6", "2", "1", "", "0.82", "y"]
        input_gen = iter(inputs)

        plan = self.planner.interactive_session(input_func=lambda _: next(input_gen), print_func=lambda *_: None)
        self.assertIsNone(plan.language)

    def test_interactive_session_verbatim_args(self):
        # Mock user inputs with verbatim keys instead of numeric indices:
        # [1] custom doc path: 'src/e2e/Dokument 5.pdf'
        # [2] verbatim taxonomy: 'multicolumn_article'
        # [3] verbatim target: 'rapid_approximate'
        # [4] verbatim security: 'hosted_vision_api'
        # [5] lang: 'pl', threshold: '0.80'
        # Override prompt: 'y'
        inputs = ["src/e2e/Dokument 5.pdf", "multicolumn_article", "rapid_approximate", "hosted_vision_api", "pl", "0.80", "y"]
        input_gen = iter(inputs)

        def mock_input(prompt=""):
            return next(input_gen)

        messages = []
        def mock_print(*args):
            messages.append(" ".join(str(a) for a in args))

        plan = self.planner.interactive_session(input_func=mock_input, print_func=mock_print)
        self.assertEqual(plan.document_path, "src/e2e/Dokument 5.pdf")
        self.assertEqual(plan.taxonomy, "multicolumn_article")
        self.assertEqual(plan.target, "rapid_approximate")
        self.assertEqual(plan.security, "hosted_vision_api")
        self.assertEqual(plan.language, "pl")
        self.assertEqual(plan.target_threshold, 0.80)
        self.assertFalse(plan.overridden)

    def test_run_pipeline_with_plan(self):
        plan = self.planner.create_plan(
            document_path="non_existent.pdf",
            taxonomy="financial_report",
            target="high_precision_structure",
            security="air_gapped_local",
            language="pl",
            target_threshold=0.82
        )
        res = run_pipeline(
            pdf_path="non_existent.pdf",
            plan=plan,
            output_dir="test_output",
            visualize=False
        )
        self.assertIn("plan", res)
        self.assertIsNotNone(res["plan"])
        self.assertEqual(res["decision"]["chosen_preset"], "docling_deep")
        self.assertTrue(res["decision"]["is_accepted"])

    def test_planner_criteria_model(self):
        criteria = PlannerCriteria(
            taxonomy="financial_report",
            target="high_precision_structure",
            security="air_gapped_local"
        )
        self.assertEqual(criteria.values(), ["financial_report", "high_precision_structure", "air_gapped_local"])
        d = criteria.to_dict()
        self.assertEqual(d["taxonomy"], "financial_report")
        restored = PlannerCriteria.from_dict(d)
        self.assertEqual(restored.taxonomy, criteria.taxonomy)
        self.assertEqual(restored.target, criteria.target)
        self.assertEqual(restored.security, criteria.security)

    def test_calculate_scores_with_criteria_object(self):
        criteria = PlannerCriteria(
            taxonomy="financial_report",
            target="high_precision_structure",
            security="air_gapped_local"
        )
        scores = self.planner.calculate_scores(criteria=criteria)
        self.assertGreater(scores["docling_deep"], scores["docling_fast"])

    def test_create_plan_with_criteria_object(self):
        criteria = PlannerCriteria(
            taxonomy="general_text",
            target="rapid_approximate",
            security="air_gapped_local"
        )
        plan = self.planner.create_plan(criteria=criteria, language="en")
        self.assertEqual(plan.primary_preset, "docling_fast")
        self.assertEqual(plan.criteria.taxonomy, "general_text")
        self.assertEqual(plan.taxonomy, "general_text")
        cfg = plan.to_ingestion_config()
        self.assertIsInstance(cfg, IngestionConfig)
        self.assertEqual(cfg.preset, "docling_fast")
        self.assertEqual(cfg.language, "en")

    def test_ingestion_config_model(self):
        cfg = IngestionConfig(
            target_threshold=0.85,
            language="pl",
            preset="docling_deep",
            align_skew=False,
            visualize=False,
            ocr_scale=3.0,
            force_full_page_ocr=True,
            do_table_structure=False
        )
        d = cfg.to_dict()
        self.assertEqual(d["preset"], "docling_deep")
        self.assertEqual(d["ocr_scale"], 3.0)
        restored = IngestionConfig.from_dict(d)
        self.assertEqual(restored.target_threshold, 0.85)
        self.assertEqual(restored.language, "pl")
        self.assertEqual(restored.preset, "docling_deep")
        self.assertFalse(restored.align_skew)
        self.assertFalse(restored.visualize)
        self.assertEqual(restored.ocr_scale, 3.0)
        self.assertTrue(restored.force_full_page_ocr)
        self.assertFalse(restored.do_table_structure)

    def test_run_pipeline_with_ingestion_config(self):
        cfg = IngestionConfig(
            target_threshold=0.82,
            language="pl",
            preset="docling_deep",
            visualize=False,
            output_dir="test_output"
        )
        res = run_pipeline(
            pdf_path="non_existent.pdf",
            config=cfg,
        )
        self.assertEqual(res["decision"]["chosen_preset"], "docling_deep")
        self.assertTrue(res["decision"]["is_accepted"])


if __name__ == "__main__":
    unittest.main()
