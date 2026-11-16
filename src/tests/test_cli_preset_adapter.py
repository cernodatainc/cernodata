"""
src/tests/test_cli_preset_adapter.py

Unit tests for SubprocessCliPresetAdapter and SectionOCRParser CLI subprocess engine.
Uses sys.executable -c as a cross-platform mock binary.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from PIL import Image

from src.parsers.section_ocr import SectionOCRParser
from src.pipeline.parsers.adapters import ParserExecutionOptions
from src.pipeline.parsers.cli_adapter import SubprocessCliPresetAdapter
from src.schemas.custom_preset import CustomPresetConfig, ParameterWiggleSpec, PresetBackendType


class TestSubprocessCliPresetAdapter(unittest.TestCase):
    """Tests CLI subprocess OCR adapter across text, markdown, and cernodata_dom_json outputs."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_cli_adapter_")
        self.dummy_pdf = os.path.join(self.test_dir, "sample.pdf")
        with open(self.dummy_pdf, "wb") as fp:
            fp.write(b"%PDF-1.4\n%mock\n")

    def tearDown(self) -> None:
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_can_handle_exact_preset_only(self) -> None:
        cfg = CustomPresetConfig(
            preset_id="my_cli_ocr",
            display_name="My CLI OCR",
            backend_type=PresetBackendType.CLI_SUBPROCESS,
            command_template=[sys.executable, "-c", "print('ok')"],
        )
        adapter = SubprocessCliPresetAdapter(cfg)
        self.assertTrue(adapter.can_handle("my_cli_ocr"))
        self.assertFalse(adapter.can_handle("docling_fast"))
        self.assertFalse(adapter.can_handle("other_cli_ocr"))

    def test_parse_plain_text_written_to_output_path(self) -> None:
        script = (
            "import sys; "
            "open(sys.argv[2], 'w', encoding='utf-8').write('First paragraph.\\n\\nSecond paragraph.')"
        )
        cfg = CustomPresetConfig(
            preset_id="cli_text",
            display_name="CLI Text",
            backend_type=PresetBackendType.CLI_SUBPROCESS,
            command_template=[sys.executable, "-c", script, "{input_path}", "{output_path}"],
            output_format="text",
        )
        adapter = SubprocessCliPresetAdapter(cfg)
        dom = adapter.parse(self.dummy_pdf, ParserExecutionOptions(preset="cli_text", language="en"))

        self.assertEqual(dom.source_filename, "sample.pdf")
        self.assertEqual(len(dom.nodes), 2)
        self.assertEqual(dom.nodes[0].type, "paragraph")
        self.assertEqual(dom.nodes[0].content["raw_text"], "First paragraph.")
        self.assertEqual(dom.nodes[1].content["raw_text"], "Second paragraph.")

    def test_parse_markdown_headings_and_tables(self) -> None:
        md_script = (
            "import sys; "
            "md = '# Quarterly Report\\n\\nSummary line.\\n\\n"
            "| Metric | Value |\\n| --- | --- |\\n| Revenue | 100 |\\n'; "
            "open(sys.argv[1], 'w', encoding='utf-8').write(md)"
        )
        adapter = SubprocessCliPresetAdapter(
            "cli_md",
            command_template=[sys.executable, "-c", md_script, "{output_path}"],
            output_format="markdown",
        )
        dom = adapter.parse(self.dummy_pdf, ParserExecutionOptions(preset="cli_md"))
        types = [n.type for n in dom.nodes]
        self.assertEqual(types, ["heading", "paragraph", "table_grid"])
        self.assertEqual(dom.nodes[0].content["raw_text"], "Quarterly Report")
        self.assertEqual(dom.nodes[0].content["level"], 1)
        self.assertEqual(dom.nodes[2].content["headers"], ["Metric", "Value"])
        self.assertEqual(dom.nodes[2].content["rows"], [["Revenue", "100"]])

    def test_parse_cernodata_dom_json_from_stdout(self) -> None:
        dom_payload = {
            "document_id": "custom_doc_1",
            "source_filename": "sample.pdf",
            "total_pages": 2,
            "nodes": [
                {
                    "node_id": "n_custom_1",
                    "type": "heading",
                    "global_page_index": 2,
                    "temp_slice_index": 2,
                    "bounding_box": {"x0": 10.0, "y0": 20.0, "x1": 200.0, "y1": 50.0},
                    "content": {"raw_text": "Page Two Title"},
                }
            ],
        }
        script = f"import json; print(json.dumps({json.dumps(dom_payload)}))"
        adapter = SubprocessCliPresetAdapter(
            "cli_dom",
            command_template=[sys.executable, "-c", script],
            output_format="cernodata_dom_json",
        )
        dom = adapter.parse(self.dummy_pdf, ParserExecutionOptions(preset="cli_dom"))
        self.assertEqual(dom.document_id, "custom_doc_1")
        self.assertEqual(dom.total_pages, 2)
        self.assertEqual(len(dom.nodes), 1)
        self.assertEqual(dom.nodes[0].node_id, "n_custom_1")
        self.assertEqual(dom.nodes[0].content["raw_text"], "Page Two Title")

    def test_wiggle_extra_parameters_passed_to_cli(self) -> None:
        script = (
            "import sys; "
            "psm = sys.argv[sys.argv.index('--psm') + 1] if '--psm' in sys.argv else 'none'; "
            "open(sys.argv[1], 'w', encoding='utf-8').write(f'mode={psm}')"
        )
        cfg = CustomPresetConfig(
            preset_id="cli_wiggle",
            display_name="CLI Wiggle",
            backend_type=PresetBackendType.CLI_SUBPROCESS,
            command_template=[sys.executable, "-c", script, "{output_path}", "--psm", "{psm}"],
            wiggle_parameters=[ParameterWiggleSpec(name="psm", default_value="3", fallback_values=["6", "11"])],
        )
        adapter = SubprocessCliPresetAdapter(cfg)
        dom_default = adapter.parse(self.dummy_pdf, ParserExecutionOptions(preset="cli_wiggle"))
        self.assertEqual(dom_default.nodes[0].content["raw_text"], "mode=3")

        dom_wiggled = adapter.parse(
            self.dummy_pdf,
            ParserExecutionOptions(preset="cli_wiggle", extra_parameters={"psm": "11"}),
        )
        self.assertEqual(dom_wiggled.nodes[0].content["raw_text"], "mode=11")

    def test_nonzero_exit_raises_runtime_error(self) -> None:
        adapter = SubprocessCliPresetAdapter(
            "cli_fail",
            command_template=[sys.executable, "-c", "import sys; sys.stderr.write('boom'); sys.exit(2)"],
        )
        with self.assertRaises(RuntimeError) as ctx:
            adapter.parse(self.dummy_pdf, ParserExecutionOptions(preset="cli_fail"))
        self.assertIn("boom", str(ctx.exception))

    def test_section_ocr_cli_subprocess_engine(self) -> None:
        parser = SectionOCRParser(language="en")
        script = "import sys; open(sys.argv[1], 'w', encoding='utf-8').write('Cutout Text 42')"
        engine = parser._create_cli_subprocess_engine([sys.executable, "-c", script, "{output_path}"])
        parser.register_engine("mock_cli_tool", engine)

        img = Image.new("RGB", (80, 30), color="white")
        res = parser.parse_image(img, engine_name="mock_cli_tool")
        self.assertTrue(res["success"])
        self.assertEqual(res["text"], "Cutout Text 42")


if __name__ == "__main__":
    unittest.main()
