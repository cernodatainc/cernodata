"""
src/tests/test_custom_preset_schema.py

Unit tests for CustomPresetConfig, ParameterWiggleSpec, PresetBackendType,
validation rules, and persistence helpers.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from src.schemas import (
    CustomPresetConfig,
    ParameterWiggleSpec,
    PresetBackendType,
)
from src.schemas.custom_preset import (
    get_community_preset_recipes,
    load_custom_presets_file,
    save_custom_presets_file,
)


class TestCustomPresetSchema(unittest.TestCase):
    """Validates custom preset schema dataclasses, validation, and JSON serialization."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_custom_preset_schema_")

    def tearDown(self) -> None:
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_cli_preset_round_trip(self) -> None:
        cfg = CustomPresetConfig(
            preset_id="tesseract_pl",
            display_name="Tesseract Polish OCR",
            backend_type=PresetBackendType.CLI_SUBPROCESS,
            command_template=["tesseract", "{input_path}", "{output_path}", "-l", "pol"],
            endpoint_url=None,
            output_format="text",
            hardware_weight="light_cpu",
            timeout_sec=90,
            wiggle_parameters=[
                ParameterWiggleSpec(name="psm", default_value="3", fallback_values=["6", "11"]),
            ],
            suitability_weights={"scanned_form": 0.92},
            taxonomy_hints=["scanned_form"],
            description="Custom Polish Tesseract OCR",
        )
        as_dict = cfg.to_dict()
        self.assertEqual(as_dict["preset_id"], "tesseract_pl")
        self.assertEqual(as_dict["backend_type"], "cli_subprocess")
        self.assertEqual(as_dict["wiggle_parameters"][0]["fallback_values"], ["6", "11"])

        restored = CustomPresetConfig.from_dict(as_dict)
        self.assertEqual(restored.preset_id, "tesseract_pl")
        self.assertEqual(restored.backend_type, PresetBackendType.CLI_SUBPROCESS)
        self.assertEqual(restored.command_template, ["tesseract", "{input_path}", "{output_path}", "-l", "pol"])
        self.assertEqual(restored.wiggle_parameters[0].name, "psm")
        self.assertEqual(restored.wiggle_parameters[0].fallback_values, ["6", "11"])
        self.assertEqual(restored.suitability_weights["scanned_form"], 0.92)
        self.assertEqual(restored.taxonomy_hints, ["scanned_form"])

    def test_http_preset_from_dict_and_python_callable(self) -> None:
        http_cfg = CustomPresetConfig.from_dict({
            "preset_id": "paddle_http",
            "display_name": "PaddleOCR HTTP",
            "backend_type": "http_endpoint",
            "endpoint_url": "http://127.0.0.1:8080/ocr",
            "output_format": "cernodata_dom_json",
            "hardware_weight": "gpu_vram",
            "timeout_sec": 60,
        })
        self.assertEqual(http_cfg.backend_type, PresetBackendType.HTTP_ENDPOINT)
        self.assertEqual(http_cfg.endpoint_url, "http://127.0.0.1:8080/ocr")
        self.assertEqual(http_cfg.output_format, "cernodata_dom_json")
        self.assertEqual(http_cfg.hardware_weight, "gpu_vram")

        py_cfg = CustomPresetConfig(
            preset_id="py_hook",
            display_name="Python Callable",
            backend_type=PresetBackendType.PYTHON_CALLABLE,
            output_format="markdown",
            hardware_weight="heavy_cpu",
        )
        self.assertEqual(py_cfg.backend_type, PresetBackendType.PYTHON_CALLABLE)

    def test_validation_errors(self) -> None:
        with self.assertRaises(ValueError):
            CustomPresetConfig(
                preset_id="",
                display_name="Invalid",
                backend_type=PresetBackendType.CLI_SUBPROCESS,
                command_template=["echo"],
            )

        with self.assertRaises(ValueError):
            CustomPresetConfig(
                preset_id="missing_cmd",
                display_name="Missing Command",
                backend_type=PresetBackendType.CLI_SUBPROCESS,
                command_template=None,
            )

        with self.assertRaises(ValueError):
            CustomPresetConfig(
                preset_id="bad_url",
                display_name="Bad URL",
                backend_type=PresetBackendType.HTTP_ENDPOINT,
                endpoint_url="ftp://localhost/ocr",
            )

        with self.assertRaises(ValueError):
            CustomPresetConfig.from_dict({
                "preset_id": "bad_fmt",
                "display_name": "Bad Format",
                "backend_type": "cli_subprocess",
                "command_template": ["tesseract"],
                "output_format": "xml",
            })

        with self.assertRaises(ValueError):
            CustomPresetConfig.from_dict({
                "preset_id": "bad_hw",
                "display_name": "Bad Hardware",
                "backend_type": "cli_subprocess",
                "command_template": ["tesseract"],
                "hardware_weight": "quantum_tpu",
            })

        with self.assertRaises(ValueError):
            CustomPresetConfig.from_dict({
                "preset_id": "bad_backend",
                "display_name": "Bad Backend",
                "backend_type": "grpc_stream",
            })

        with self.assertRaises(ValueError):
            ParameterWiggleSpec.from_dict({"name": "", "fallback_values": ["a"]})

        with self.assertRaises(ValueError):
            ParameterWiggleSpec.from_dict({"name": "psm", "fallback_values": "not_a_list"})

    def test_save_and_load_custom_presets_file(self) -> None:
        file_path = os.path.join(self.test_dir, "custom_presets.json")
        self.assertEqual(load_custom_presets_file(file_path), [])

        presets = [
            CustomPresetConfig(
                preset_id="custom_cli",
                display_name="Custom CLI",
                backend_type=PresetBackendType.CLI_SUBPROCESS,
                command_template=["tesseract", "{input_path}", "{output_path}"],
            ),
            CustomPresetConfig(
                preset_id="custom_http",
                display_name="Custom HTTP",
                backend_type=PresetBackendType.HTTP_ENDPOINT,
                endpoint_url="http://127.0.0.1:9001/ocr",
            ),
        ]
        save_custom_presets_file(file_path, presets)
        loaded = load_custom_presets_file(file_path)
        self.assertEqual(len(loaded), 2)
        self.assertEqual([p.preset_id for p in loaded], ["custom_cli", "custom_http"])

        # Also verify {"presets": [...]} wrapper format and skipping invalid entries
        wrapped_path = os.path.join(self.test_dir, "wrapped.json")
        with open(wrapped_path, "w", encoding="utf-8") as fp:
            json.dump({"presets": [presets[0].to_dict(), {"preset_id": "broken"}]}, fp)
        wrapped_loaded = load_custom_presets_file(wrapped_path)
        self.assertEqual(len(wrapped_loaded), 1)
        self.assertEqual(wrapped_loaded[0].preset_id, "custom_cli")

    def test_community_recipes_available(self) -> None:
        recipes = get_community_preset_recipes()
        ids = {r.preset_id for r in recipes}
        self.assertTrue({
            "tesseract_multilang",
            "ocrmypdf_deskew",
            "marker_scientific_md",
            "paddleocr_cjk_http",
            "kraken_historical_handwriting",
        }.issubset(ids))


if __name__ == "__main__":
    unittest.main()
