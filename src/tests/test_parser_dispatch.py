"""
src/tests/test_parser_dispatch.py

Unit tests for modular parser adapters, parser registry, and progress notification.
"""

import unittest
from unittest.mock import MagicMock, patch

from src.dom import DocumentDOM
from src.pipeline.parsers.adapters import (
    DoclingPresetAdapter,
    ParserExecutionOptions,
    PyPdfiumPresetAdapter,
)
from src.pipeline.parsers.registry import ParserPresetRegistry
from src.pipeline.parsers.dispatch import DocumentParserDispatcher
from src.pipeline.planner.models import IngestionConfig
from src.pipeline.progress_notifier import PipelineProgressNotifier
from src.pipeline.config_resolver import PipelineConfigResolver


class TestModularParserDispatch(unittest.TestCase):

    def test_parser_execution_options_from_inputs(self):
        opts = ParserExecutionOptions.from_inputs(
            language="pl",
            preset="docling_fast",
            ocr_scale=2.5,
        )
        self.assertEqual(opts.language, "pl")
        self.assertEqual(opts.preset, "docling_fast")
        self.assertEqual(opts.ocr_scale, 2.5)
        self.assertFalse(opts.force_full_page_ocr)

    def test_parser_execution_options_from_config(self):
        cfg = IngestionConfig(
            language="de",
            preset="pypdfium_rapidocr",
            ocr_scale=3.5,
            force_full_page_ocr=True,
        )
        opts = ParserExecutionOptions.from_inputs(config=cfg)
        self.assertEqual(opts.language, "de")
        self.assertEqual(opts.preset, "pypdfium_rapidocr")
        self.assertEqual(opts.ocr_scale, 3.5)
        self.assertTrue(opts.force_full_page_ocr)

    def test_parser_adapters_can_handle(self):
        pypdfium_adapter = PyPdfiumPresetAdapter()
        docling_adapter = DoclingPresetAdapter()

        self.assertTrue(pypdfium_adapter.can_handle("pypdfium_rapidocr"))
        self.assertFalse(pypdfium_adapter.can_handle("docling_fast"))

        self.assertTrue(docling_adapter.can_handle("docling_fast"))
        self.assertTrue(docling_adapter.can_handle("docling_deep"))
        self.assertTrue(docling_adapter.can_handle("any_custom_preset"))

    def test_custom_parser_registry_registration(self):
        registry = ParserPresetRegistry()
        mock_adapter = MagicMock()
        mock_adapter.can_handle.side_effect = lambda p: p == "custom_preset"

        registry.register(mock_adapter)
        self.assertIs(registry.resolve("custom_preset"), mock_adapter)
        self.assertIsNone(registry.resolve("unknown_preset"))

    def test_dispatcher_with_mock_registry(self):
        mock_dom = DocumentDOM(document_id="d1", source_filename="sample.pdf", total_pages=1, nodes=[])
        mock_registry = MagicMock()
        mock_registry.execute.return_value = mock_dom

        dispatcher = DocumentParserDispatcher(registry=mock_registry)
        with patch("src.pipeline.parsers.dispatch.resolve_pdf_path", return_value="dummy.pdf"), \
             patch("os.path.exists", return_value=True):
            res = dispatcher.parse("dummy.pdf", preset="pypdfium_rapidocr")
            self.assertIs(res, mock_dom)
            mock_registry.execute.assert_called_once()

    def test_progress_notifier_invokes_callback_safely(self):
        events = []

        def callback(pct: int, step: str, msg: str) -> None:
            events.append((pct, step, msg))

        notifier = PipelineProgressNotifier(callback)
        notifier.notify_initiation("doc.pdf", "docling_fast", "en")
        notifier.notify_preset_execution("docling_fast")
        notifier.notify_verification()
        notifier.notify_preset_switching(
            target_preset="docling_deep",
            current_preset="docling_fast",
            confidence=0.54,
            threshold=0.85,
        )
        notifier.notify_preset_execution("docling_deep", pct=80)
        notifier.notify_complete("ACCEPT", 0.95, 0)

        self.assertEqual(len(events), 6)
        self.assertEqual(events[0][0], 20)
        self.assertEqual(events[1][0], 40)
        self.assertEqual(events[1][1], "running docling_fast")
        self.assertEqual(events[2][0], 65)
        self.assertEqual(events[3][0], 75)
        self.assertEqual(events[3][1], "docling_fast confidence too low (0.54 < 0.85), starting docling_deep")
        self.assertEqual(events[4][0], 80)
        self.assertEqual(events[4][1], "running docling_deep")
        self.assertEqual(events[5][0], 100)

    def test_progress_notifier_swallows_callback_exceptions(self):
        def bad_callback(pct: int, step: str, msg: str) -> None:
            raise RuntimeError("UI socket closed")

        notifier = PipelineProgressNotifier(bad_callback)
        # Should not raise exception
        notifier.notify(50, "test", "test")

    def test_config_resolver_resolves_request(self):
        pdf_path, cfg, plan = PipelineConfigResolver.resolve_request(
            pdf_path="test.pdf",
            preset="docling_deep",
            target_threshold=0.88,
        )
        self.assertEqual(pdf_path, "test.pdf")
        self.assertEqual(cfg.preset, "docling_deep")
        self.assertEqual(cfg.target_threshold, 0.88)
        self.assertIsNone(plan)

    def test_cli_progress_reporter(self):
        import io
        from unittest.mock import patch
        from src.main import CliProgressReporter

        reporter = CliProgressReporter()
        buf = io.StringIO()
        with patch("sys.stdout.write", side_effect=buf.write):
            reporter(40, "running docling_fast", "Running extraction with preset 'docling_fast'...")
            reporter(75, "docling_fast confidence too low (0.54 < 0.85), starting docling_deep", "switch")
            reporter(80, "running docling_deep", "Running extraction with preset 'docling_deep'...")

        out = buf.getvalue()
        self.assertIn("running docling_fast", out)
        self.assertIn("docling_fast confidence too low (0.54 < 0.85), starting docling_deep", out)
        self.assertIn("running docling_deep", out)
        self.assertIn("[|]", out)
        self.assertIn("[/]", out)


if __name__ == "__main__":
    unittest.main()
