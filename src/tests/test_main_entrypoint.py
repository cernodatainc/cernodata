"""
src/tests/test_main_entrypoint.py

Unit tests for consolidated CLI flags and entrypoint execution in main.py and src/main.py.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import main as root_main
from src.main import create_parser, main as src_main, parse_args


class TestMainEntrypoint(unittest.TestCase):
    """Test suite verifying consolidated flags and server startup behavior."""

    def test_create_parser(self) -> None:
        """Verifies that create_parser returns an ArgumentParser instance."""
        parser = create_parser()
        self.assertIsNotNone(parser)
        self.assertEqual(parser.prog, "cernodata")

    def test_default_flags_configured_for_server(self) -> None:
        """Verifies that default arguments configure the server hub without batch mode."""
        args = parse_args([])
        self.assertEqual(args.port, 8000)
        self.assertEqual(args.browser_port, 8000)
        self.assertEqual(args.host, "127.0.0.1")
        self.assertFalse(args.no_browser)
        self.assertTrue(args.serve)
        self.assertFalse(args.batch)
        self.assertIsNone(args.input)
        self.assertEqual(args.language, "en")
        self.assertAlmostEqual(args.target_threshold, 0.82)
        self.assertEqual(args.output_dir, "output")
        self.assertFalse(args.no_align_skew)
        self.assertFalse(args.no_visuals)

    def test_flag_aliases_port(self) -> None:
        """Verifies that -p, --port, and --browser-port all resolve to the same port."""
        args_short = parse_args(["-p", "9050"])
        self.assertEqual(args_short.port, 9050)
        self.assertEqual(args_short.browser_port, 9050)

        args_long = parse_args(["--port", "9060"])
        self.assertEqual(args_long.port, 9060)
        self.assertEqual(args_long.browser_port, 9060)

        args_legacy = parse_args(["--browser-port", "9070"])
        self.assertEqual(args_legacy.port, 9070)
        self.assertEqual(args_legacy.browser_port, 9070)

    def test_flag_aliases_input_and_preset(self) -> None:
        """Verifies aliases for document input (-i, --input, --pdf) and preset (--preset, --override-preset)."""
        args_i = parse_args(["-i", "doc1.pdf"])
        self.assertEqual(args_i.input, "doc1.pdf")

        args_input = parse_args(["--input", "doc2.pdf"])
        self.assertEqual(args_input.input, "doc2.pdf")

        args_pdf = parse_args(["--pdf", "doc3.pdf"])
        self.assertEqual(args_pdf.input, "doc3.pdf")

        args_preset = parse_args(["--preset", "docling_deep"])
        self.assertEqual(args_preset.override_preset, "docling_deep")

        args_override = parse_args(["--override-preset", "vision_llm_direct"])
        self.assertEqual(args_override.override_preset, "vision_llm_direct")

    def test_batch_and_terminal_flags(self) -> None:
        """Verifies batch execution and terminal questionnaire flags."""
        args_batch = parse_args(["--batch"])
        self.assertTrue(args_batch.batch)

        args_cli = parse_args(["--cli"])
        self.assertTrue(args_cli.cli)

        args_term = parse_args(["--terminal"])
        self.assertTrue(args_term.cli)

    @patch("src.pipeline.server.start_pipeline_server")
    def test_default_invocation_starts_server(self, mock_start_server: MagicMock) -> None:
        """Verifies that 'python main.py' with default arguments starts the pipeline server."""
        src_main([])
        mock_start_server.assert_called_once_with(
            pdf_path="",
            language="en",
            port=8000,
            open_browser=True,
        )

    @patch("src.pipeline.server.start_pipeline_server")
    def test_root_main_default_invocation_starts_server(self, mock_start_server: MagicMock) -> None:
        """Verifies that root main.py invocation starts the pipeline server."""
        root_main.main([])
        mock_start_server.assert_called_once_with(
            pdf_path="",
            language="en",
            port=8000,
            open_browser=True,
        )

    @patch("src.pipeline.server.start_pipeline_server")
    def test_invocation_with_custom_port_and_no_browser(self, mock_start_server: MagicMock) -> None:
        """Verifies custom port and no-browser options are forwarded to start_pipeline_server."""
        src_main(["--port", "8888", "--no-browser", "-i", "sample.pdf"])
        mock_start_server.assert_called_once_with(
            pdf_path="sample.pdf",
            language="en",
            port=8888,
            open_browser=False,
        )

    @patch("src.pipeline.server.start_pipeline_server")
    def test_reexport_from_cli_module(self, mock_start_server: MagicMock) -> None:
        """Verifies src.cli re-exports create_parser and parse_args."""
        from src.cli import create_parser as cli_create_parser, parse_args as cli_parse_args
        parser = cli_create_parser()
        self.assertIsNotNone(parser)
        args = cli_parse_args(["--port", "8500"])
        self.assertEqual(args.port, 8500)


if __name__ == "__main__":
    unittest.main()
