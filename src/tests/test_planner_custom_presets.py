"""
src/tests/test_planner_custom_presets.py

Unit tests for TASK-205: merging CustomPresetConfig suitability weights
into PresetPlanner and verifying custom presets participate in scoring and planning.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from src.pipeline.planner.options import DEFAULT_PRESET_WEIGHTS
from src.pipeline.planner.planner import PresetPlanner
from src.schemas.custom_preset import (
    CustomPresetConfig,
    PresetBackendType,
    save_custom_presets_file,
)


class TestPlannerCustomPresets(unittest.TestCase):
    """Tests PresetPlanner weight derivation, loading, and plan ranking for custom presets."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_planner_custom_")

    def tearDown(self) -> None:
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_derive_weights_from_hardware_backend_and_taxonomy_hints(self) -> None:
        cli_cfg = CustomPresetConfig(
            preset_id="local_kraken",
            display_name="Local Kraken",
            backend_type=PresetBackendType.CLI_SUBPROCESS,
            command_template=["kraken", "{input_path}", "{output_path}"],
            hardware_weight="heavy_cpu",
            taxonomy_hints=["scanned_form"],
        )
        derived = PresetPlanner.derive_custom_preset_weights(cli_cfg)
        self.assertGreater(derived["scanned_form"], derived["financial_report"])
        self.assertGreater(derived["air_gapped_local"], derived["hosted_vision_api"])
        self.assertGreater(derived["high_precision_structure"], derived["rapid_approximate"])

        http_cfg = CustomPresetConfig(
            preset_id="remote_paddle",
            display_name="Remote Paddle",
            backend_type=PresetBackendType.HTTP_ENDPOINT,
            endpoint_url="http://127.0.0.1:8866/ocr",
            hardware_weight="gpu_vram",
            suitability_weights={"tabular_ledger": 0.99, "hosted_vision_api": 0.95},
        )
        http_derived = PresetPlanner.derive_custom_preset_weights(http_cfg)
        self.assertEqual(http_derived["tabular_ledger"], 0.99)
        self.assertEqual(http_derived["hosted_vision_api"], 0.95)
        self.assertLess(http_derived["air_gapped_local"], 0.5)

    def test_planner_merges_custom_presets_without_mutating_defaults(self) -> None:
        default_keys_before = set(DEFAULT_PRESET_WEIGHTS.keys())
        custom_cfg = CustomPresetConfig(
            preset_id="dominant_custom_ocr",
            display_name="Dominant Custom OCR",
            backend_type=PresetBackendType.CLI_SUBPROCESS,
            command_template=["tesseract", "{input_path}", "{output_path}"],
            suitability_weights={
                "financial_report": 0.99,
                "high_precision_structure": 0.99,
                "air_gapped_local": 0.99,
            },
        )
        planner = PresetPlanner(custom_presets=[custom_cfg])
        self.assertIn("dominant_custom_ocr", planner.weights)
        self.assertEqual(set(DEFAULT_PRESET_WEIGHTS.keys()), default_keys_before)

        plan = planner.create_plan(
            document_path="invoice.pdf",
            taxonomy="financial_report",
            target="high_precision_structure",
            security="air_gapped_local",
        )
        self.assertEqual(plan.primary_preset, "dominant_custom_ocr")
        self.assertEqual(plan.suggested_order[0], "dominant_custom_ocr")
        self.assertAlmostEqual(plan.scores["dominant_custom_ocr"], 0.99, places=3)

    def test_planner_loads_custom_presets_from_json_path(self) -> None:
        manifest = os.path.join(self.test_dir, "custom_presets.json")
        cfg = CustomPresetConfig(
            preset_id="manifest_http_ocr",
            display_name="Manifest HTTP OCR",
            backend_type=PresetBackendType.HTTP_ENDPOINT,
            endpoint_url="http://127.0.0.1:9001/ocr",
            suitability_weights={
                "scanned_form": 0.96,
                "rapid_approximate": 0.96,
                "hosted_vision_api": 0.96,
            },
        )
        save_custom_presets_file(manifest, [cfg])

        planner = PresetPlanner(custom_presets_path=manifest)
        scores = planner.calculate_scores(
            taxonomy="scanned_form",
            target="rapid_approximate",
            security="hosted_vision_api",
        )
        self.assertIn("manifest_http_ocr", scores)
        self.assertAlmostEqual(scores["manifest_http_ocr"], 0.96, places=3)


if __name__ == "__main__":
    unittest.main()
