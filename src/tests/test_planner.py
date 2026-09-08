"""
src/tests/test_planner.py

Unit tests for PresetPlanner, DocumentPlan serialization, override behavior,
and plan-driven pipeline execution.
"""

import os
import unittest
from src.pipeline.planner import PresetPlanner, DocumentPlan
from src.pipeline.orchestrator import run_pipeline


class TestPlanner(unittest.TestCase):

    def setUp(self):
        self.planner = PresetPlanner()

    def test_calculate_scores_low_spec_cpu(self):
        scores = self.planner.calculate_scores(
            taxonomy="general_text",
            hardware="low_spec_cpu",
            target="rapid_approximate",
            security="air_gapped_local"
        )
        self.assertIn("docling_fast", scores)
        self.assertIn("docling_deep", scores)
        self.assertIn("vision_llm_direct", scores)
        # On low spec CPU and rapid approximate, docling_fast should rank higher
        self.assertGreater(scores["docling_fast"], scores["vision_llm_direct"])

    def test_calculate_scores_workstation_cuda(self):
        scores = self.planner.calculate_scores(
            taxonomy="financial_report",
            hardware="workstation_cuda",
            target="high_precision_structure",
            security="air_gapped_local"
        )
        # On workstation CUDA with financial report, docling_deep should rank top
        self.assertGreater(scores["docling_deep"], scores["docling_fast"])
        suggested = self.planner.suggest_preset_order(scores)
        self.assertEqual(suggested[0], "docling_deep")

    def test_create_plan_default(self):
        plan = self.planner.create_plan(
            document_path="src/e2e/Dokument 5.pdf",
            taxonomy="financial_report",
            hardware="workstation_cuda",
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
            hardware="workstation_cuda",
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
        # Mock user inputs:
        # [1] custom doc path: 'src/e2e/Dokument 5.pdf'
        # [2] choice 1 (financial_report)
        # [3] choice 2 (workstation_cuda)
        # [4] choice 2 (high_precision_structure)
        # [5] choice 1 (air_gapped_local)
        # [6] lang: 'pl', threshold: '0.85'
        # Override prompt: 'y'
        inputs = ["src/e2e/Dokument 5.pdf", "1", "2", "2", "1", "pl", "0.85", "y"]
        input_gen = iter(inputs)

        def mock_input(prompt=""):
            return next(input_gen)

        messages = []
        def mock_print(*args):
            messages.append(" ".join(str(a) for a in args))

        plan = self.planner.interactive_session(input_func=mock_input, print_func=mock_print)
        self.assertEqual(plan.document_path, "src/e2e/Dokument 5.pdf")
        self.assertEqual(plan.taxonomy, "financial_report")
        self.assertEqual(plan.hardware, "workstation_cuda")
        self.assertEqual(plan.language, "pl")
        self.assertEqual(plan.target_threshold, 0.85)
        self.assertEqual(plan.primary_preset, "docling_deep")
        self.assertFalse(plan.overridden)

    def test_interactive_session_verbatim_args(self):
        # Mock user inputs with verbatim keys instead of numeric indices:
        # [1] custom doc path: 'src/e2e/Dokument 5.pdf'
        # [2] verbatim taxonomy: 'multicolumn_article'
        # [3] verbatim hardware: 'workstation_cuda'
        # [4] verbatim target: 'rapid_approximate'
        # [5] verbatim security: 'hosted_vision_api'
        # [6] lang: 'pl', threshold: '0.80'
        # Override prompt: 'y'
        inputs = ["src/e2e/Dokument 5.pdf", "multicolumn_article", "workstation_cuda", "rapid_approximate", "hosted_vision_api", "pl", "0.80", "y"]
        input_gen = iter(inputs)

        def mock_input(prompt=""):
            return next(input_gen)

        messages = []
        def mock_print(*args):
            messages.append(" ".join(str(a) for a in args))

        plan = self.planner.interactive_session(input_func=mock_input, print_func=mock_print)
        self.assertEqual(plan.document_path, "src/e2e/Dokument 5.pdf")
        self.assertEqual(plan.taxonomy, "multicolumn_article")
        self.assertEqual(plan.hardware, "workstation_cuda")
        self.assertEqual(plan.target, "rapid_approximate")
        self.assertEqual(plan.security, "hosted_vision_api")
        self.assertEqual(plan.language, "pl")
        self.assertEqual(plan.target_threshold, 0.80)
        self.assertFalse(plan.overridden)

    def test_run_pipeline_with_plan(self):
        plan = self.planner.create_plan(
            document_path="non_existent.pdf",
            taxonomy="financial_report",
            hardware="workstation_cuda",
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


if __name__ == "__main__":
    unittest.main()
