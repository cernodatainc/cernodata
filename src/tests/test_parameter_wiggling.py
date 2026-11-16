"""
src/tests/test_parameter_wiggling.py

End-to-end Path B parameter wiggling tests for TASK-206 through
FallbackLoopHandler, AttemptRunner, DocumentParserDispatcher,
SubprocessCliPresetAdapter, and HttpPresetAdapter.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Tuple

from src.dom import DocumentDOM
from src.parsers.section_ocr import (
    SectionOCRParser,
    get_default_section_parser,
    set_default_section_parser,
)
from src.pipeline.attempt_runner import AttemptRunner
from src.pipeline.fallback_handler import (
    ACTION_PATH_B_WIGGLE,
    FallbackLoopHandler,
)
from src.pipeline.parsers.dispatch import DocumentParserDispatcher
from src.pipeline.parsers.registry import ParserPresetRegistry
from src.pipeline.planner.models import IngestionConfig
from src.schemas.custom_preset import (
    CustomPresetConfig,
    ParameterWiggleSpec,
    PresetBackendType,
)


class _WiggleHttpHandler(BaseHTTPRequestHandler):
    """Mock HTTP endpoint whose OCR quality responds to wiggled ocr_scale parameter."""

    requests_seen: List[Dict[str, Any]] = []

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        payload = json.loads(raw) if raw else {}
        self.__class__.requests_seen.append(payload)

        params = payload.get("parameters") or {}
        scale = float(params.get("ocr_scale", 2.0))
        text = "accepted-high-res" if scale >= 3.0 else "blurry-low-res"
        body = json.dumps({"text": text}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _noop_align(dom: DocumentDOM, pdf_path: str, align_skew: bool) -> DocumentDOM:
    _ = pdf_path
    _ = align_skew
    return dom


def _noop_postprocess(
    dom: DocumentDOM,
    config: Any = None,
    pdf_path: Any = None,
) -> DocumentDOM:
    _ = config
    _ = pdf_path
    return dom


def _make_text_evaluator(accepted_token: str) -> Any:
    def _eval(
        dom: DocumentDOM,
        config: IngestionConfig,
        current_preset_score: float,
        next_preset_score: float,
        next_preset_id: Any = None,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        _ = config
        _ = current_preset_score
        _ = next_preset_score
        _ = next_preset_id
        text = dom.nodes[0].content.get("raw_text", "") if dom.nodes else ""
        if accepted_token in text:
            return (
                {
                    "is_accepted": True,
                    "overall_confidence": 0.95,
                    "decision_tree": {"action": "ACCEPT_OUTPUT", "reason": "Threshold met."},
                },
                [],
            )
        return (
            {
                "is_accepted": False,
                "overall_confidence": 0.45,
                "decision_tree": {"action": ACTION_PATH_B_WIGGLE, "reason": "Confidence too low."},
            },
            [{"code": "LOW_CONFIDENCE", "severity": "critical"}],
        )

    return _eval


class TestParameterWiggling(unittest.TestCase):
    """Tests CustomPresetConfig ParameterWiggleSpec propagation during Path B retries."""

    server: HTTPServer
    thread: threading.Thread
    http_url: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = HTTPServer(("127.0.0.1", 0), _WiggleHttpHandler)
        cls.http_url = f"http://127.0.0.1:{cls.server.server_port}/ocr"
        cls.thread = threading.Thread(
            target=lambda: cls.server.serve_forever(poll_interval=0.05),
            daemon=True,
        )
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self) -> None:
        _WiggleHttpHandler.requests_seen.clear()
        self._prev_parser = get_default_section_parser()
        set_default_section_parser(SectionOCRParser(language="en"))
        self.test_dir = tempfile.mkdtemp(prefix="test_wiggle_")
        self.dummy_pdf = os.path.join(self.test_dir, "scan.pdf")
        with open(self.dummy_pdf, "wb") as fp:
            fp.write(b"%PDF-1.4\n%wiggle\n")

    def tearDown(self) -> None:
        set_default_section_parser(self._prev_parser)
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_cli_custom_wiggle_parameters_iterated_until_accepted(self) -> None:
        script = (
            "import sys; "
            "psm = sys.argv[sys.argv.index('--psm') + 1] if '--psm' in sys.argv else '0'; "
            "open(sys.argv[1], 'w', encoding='utf-8').write(f'psm={psm}')"
        )
        cfg_preset = CustomPresetConfig(
            preset_id="cli_wiggle_ocr",
            display_name="CLI Wiggle OCR",
            backend_type=PresetBackendType.CLI_SUBPROCESS,
            command_template=[sys.executable, "-c", script, "{output_path}", "--psm", "{psm}"],
            wiggle_parameters=[
                ParameterWiggleSpec(name="psm", default_value="3", fallback_values=["6", "11"]),
            ],
        )
        registry = ParserPresetRegistry.create_default()
        registry.register_custom_preset(cfg_preset)
        dispatcher = DocumentParserDispatcher(registry=registry)

        runner = AttemptRunner(
            parse_fn=dispatcher.parse,
            align_fn=_noop_align,
            evaluate_fn=_make_text_evaluator("psm=11"),
            postprocess_fn=_noop_postprocess,
        )
        handler = FallbackLoopHandler(attempt_runner=runner)

        ing_cfg = IngestionConfig(preset="cli_wiggle_ocr", target_threshold=0.8)
        dom, decision, violations = runner.execute_attempt(self.dummy_pdf, ing_cfg, 0.9, 0.5)
        self.assertFalse(decision["is_accepted"])

        attempts: List[Dict[str, Any]] = []
        out_dom, out_decision, out_violations = handler.handle_fallback(
            self.dummy_pdf,
            ing_cfg,
            dom,
            decision,
            violations,
            attempts,
            next_candidate=None,
            part_of_plan=False,
            curr_score=0.9,
            next_score=0.5,
        )

        self.assertTrue(out_decision["is_accepted"])
        self.assertEqual(out_violations, [])
        self.assertEqual(out_dom.nodes[0].content["raw_text"], "psm=11")
        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[0]["parameters"], {"psm": "6"})
        self.assertEqual(attempts[1]["parameters"], {"psm": "11"})

    def test_http_custom_wiggle_scale_updates_config_and_endpoint_payload(self) -> None:
        cfg_preset = CustomPresetConfig(
            preset_id="http_wiggle_ocr",
            display_name="HTTP Wiggle OCR",
            backend_type=PresetBackendType.HTTP_ENDPOINT,
            endpoint_url=self.http_url,
            wiggle_parameters=[
                ParameterWiggleSpec(name="ocr_scale", default_value=2.0, fallback_values=[3.5]),
            ],
        )
        registry = ParserPresetRegistry.create_default()
        registry.register_custom_preset(cfg_preset)
        dispatcher = DocumentParserDispatcher(registry=registry)

        runner = AttemptRunner(
            parse_fn=dispatcher.parse,
            align_fn=_noop_align,
            evaluate_fn=_make_text_evaluator("accepted-high-res"),
            postprocess_fn=_noop_postprocess,
        )
        handler = FallbackLoopHandler(attempt_runner=runner)

        ing_cfg = IngestionConfig(preset="http_wiggle_ocr", target_threshold=0.8)
        scale, force_ocr = handler._resolve_wiggle_parameters(ing_cfg)
        self.assertEqual(scale, 3.5)
        self.assertTrue(force_ocr)

        dom, decision, violations = runner.execute_attempt(self.dummy_pdf, ing_cfg, 0.9, 0.5)
        self.assertFalse(decision["is_accepted"])

        attempts: List[Dict[str, Any]] = []
        out_dom, out_decision, _ = handler.handle_fallback(
            self.dummy_pdf,
            ing_cfg,
            dom,
            decision,
            violations,
            attempts,
            next_candidate=None,
            part_of_plan=False,
            curr_score=0.9,
            next_score=0.5,
        )

        self.assertTrue(out_decision["is_accepted"])
        self.assertEqual(out_dom.nodes[0].content["raw_text"], "accepted-high-res")
        self.assertEqual(attempts[0]["parameters"], {"ocr_scale": 3.5})
        self.assertEqual(_WiggleHttpHandler.requests_seen[-1]["parameters"]["ocr_scale"], 3.5)


if __name__ == "__main__":
    unittest.main()
