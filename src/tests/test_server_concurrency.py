"""
src/tests/test_server_concurrency.py

Unit tests for multi-threaded HTTP server concurrency, ServerSessionContext thread safety,
and real-time progress state reporting.
"""

from __future__ import annotations

import json
import threading
import time
import unittest
import urllib.request
from typing import Dict, Any, List

from src.utils import find_available_port
from src.pipeline.server import (
    ServerSessionContext,
    PipelineViewerServer,
    PipelineViewerHandler,
)


class TestServerSessionContext(unittest.TestCase):
    """Verifies thread-safety and behavior of ServerSessionContext."""

    def test_progress_lifecycle(self) -> None:
        session = ServerSessionContext(pdf_path="test.pdf", language="pl")
        init_state = session.get_progress()
        self.assertEqual(init_state["status"], "idle")
        self.assertEqual(init_state["progress"], 0)
        self.assertFalse(init_state["completed"])

        session.reset_progress(initial_step="Step 1: Ingestion", log="[INIT] Starting pipeline")
        reset_state = session.get_progress()
        self.assertEqual(reset_state["status"], "running")
        self.assertEqual(reset_state["progress"], 10)
        self.assertEqual(len(reset_state["logs"]), 1)

        session.update_progress(
            progress=50,
            step_index=3,
            current_step="Step 3: Quality checks",
            log="[INFO] Scanning nodes",
        )
        mid_state = session.get_progress()
        self.assertEqual(mid_state["progress"], 50)
        self.assertEqual(mid_state["step_index"], 3)
        self.assertEqual(len(mid_state["logs"]), 2)

        session.set_completed(status="ACCEPT", confidence=0.96, violations_count=1, log="[DONE] Finished")
        done_state = session.get_progress()
        self.assertEqual(done_state["status"], "completed")
        self.assertEqual(done_state["progress"], 100)
        self.assertTrue(done_state["completed"])
        self.assertEqual(len(done_state["logs"]), 3)

    def test_concurrent_progress_updates_and_reads(self) -> None:
        session = ServerSessionContext()
        session.reset_progress()
        errors: List[Exception] = []

        def writer(worker_id: int) -> None:
            try:
                for i in range(25):
                    session.update_progress(
                        progress=i * 4,
                        step_index=(i % 5) + 1,
                        current_step=f"Step {(i % 5) + 1}",
                        log=f"Worker {worker_id} update {i}",
                    )
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def reader() -> None:
            try:
                for _ in range(50):
                    progress = session.get_progress()
                    self.assertIsInstance(progress["logs"], list)
                    self.assertIn("status", progress)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads: List[threading.Thread] = []
        for w in range(3):
            threads.append(threading.Thread(target=writer, args=(w,)))
        for _ in range(3):
            threads.append(threading.Thread(target=reader))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Thread errors occurred: {errors}")


class TestPipelineViewerServerConcurrency(unittest.TestCase):
    """Verifies that the multi-threaded server handles concurrent requests without blocking."""

    server: PipelineViewerServer
    server_thread: threading.Thread
    port: int
    base_url: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.port = find_available_port(start_port=9300, max_attempts=50)
        session = ServerSessionContext(pdf_path="sample.pdf", language="en")
        cls.server = PipelineViewerServer(("127.0.0.1", cls.port), PipelineViewerHandler, session_context=session)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "server"):
            cls.server.shutdown()
            cls.server.server_close()

    def _get_json(self, path: str) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            content = response.read().decode("utf-8")
            return json.loads(content) if content else {}

    def test_progress_polling_during_simulated_pipeline_run(self) -> None:
        session = self.server.session_context
        session.reset_progress(initial_step="Starting test run", log="[INIT] Started")

        def simulate_pipeline() -> None:
            for step in range(1, 6):
                time.sleep(0.05)
                session.update_progress(
                    progress=step * 20,
                    step_index=step,
                    current_step=f"Step {step}: In progress",
                    log=f"[INFO] Step {step} completed.",
                )
            session.set_completed(status="ACCEPT", confidence=0.98, violations_count=0)

        worker = threading.Thread(target=simulate_pipeline)
        worker.start()

        # Concurrently poll /api/progress while the worker is running
        polled_percentages: List[int] = []
        for _ in range(6):
            data = self._get_json("/api/progress")
            polled_percentages.append(data.get("progress", 0))
            time.sleep(0.04)

        worker.join()

        final_data = self._get_json("/api/progress")
        self.assertEqual(final_data.get("status"), "completed")
        self.assertEqual(final_data.get("progress"), 100)
        self.assertTrue(len(polled_percentages) > 0)
