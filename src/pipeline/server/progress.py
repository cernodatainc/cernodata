"""
src/pipeline/server/progress.py

Thread-safe real-time pipeline execution progress tracking, milestone logging,
and callback generation.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from src.pipeline.server.artifacts import calculate_progress_step


class ProgressTracker:
    """
    Thread-safe container managing progress percentages, milestone status,
    and cumulative event logs for a pipeline execution session.
    """

    def __init__(self, lock: Optional[threading.RLock] = None) -> None:
        self._lock: threading.RLock = lock if lock is not None else threading.RLock()
        self.progress_state: Dict[str, Any] = {
            "status": "idle",
            "progress": 0,
            "step_index": 0,
            "current_step": "Idle - ready to execute",
            "logs": ["[INIT] Server ready. Waiting to trigger pipeline."],
            "completed": False,
            "error": None,
        }

    def get_progress(self) -> Dict[str, Any]:
        """
        Thread-safe retrieval of current progress state.

        Returns:
            Dictionary snapshot of progress state including copy of log entries.
        """
        with self._lock:
            state = dict(self.progress_state)
            state["logs"] = list(self.progress_state.get("logs", []))
            return state

    def update_progress(
        self,
        progress: int,
        step_index: int,
        current_step: str,
        log: Optional[str] = None,
        status: str = "running",
        completed: bool = False,
        error: Optional[str] = None,
    ) -> None:
        """
        Thread-safe update of progress state and log history.

        Args:
            progress: Percentage value in [0, 100].
            step_index: Pipeline step index (1..5).
            current_step: Human-readable step description.
            log: Optional log message to append.
            status: Execution status string ('running', 'completed', 'error').
            completed: Whether the overall run has finalized.
            error: Optional error description string.
        """
        with self._lock:
            self.progress_state["progress"] = progress
            self.progress_state["step_index"] = step_index
            self.progress_state["current_step"] = current_step
            self.progress_state["status"] = status
            self.progress_state["completed"] = completed
            if error is not None:
                self.progress_state["error"] = error
            if log:
                self.progress_state.setdefault("logs", []).append(log)

    def make_progress_callback(self) -> Callable[[int, str, str], None]:
        """
        Creates a standardized progress callback function wired to this tracker.

        Returns:
            Callable taking (pct, step_desc, log_msg) and updating state.
        """
        def on_progress(pct: int, step_desc: str, log_msg: str) -> None:
            t = datetime.now().strftime("%H:%M:%S")
            self.update_progress(
                progress=pct,
                step_index=calculate_progress_step(pct),
                current_step=step_desc,
                log=f"[{t}] {log_msg}",
            )

        return on_progress

    def add_log(self, message: str) -> None:
        """
        Thread-safe appending of a log message to the history.

        Args:
            message: Formatted log message string.
        """
        with self._lock:
            self.progress_state.setdefault("logs", []).append(message)

    def reset_progress(self, initial_step: str = "Starting...", log: Optional[str] = None) -> None:
        """
        Thread-safe reset of progress state to initiate a new execution run.

        Args:
            initial_step: Description for the starting milestone.
            log: Optional initial log entry.
        """
        with self._lock:
            logs: List[str] = []
            if log:
                logs.append(log)
            self.progress_state = {
                "status": "running",
                "progress": 10,
                "step_index": 1,
                "current_step": initial_step,
                "logs": logs,
                "completed": False,
                "error": None,
            }

    def set_error(self, error_msg: str, log: Optional[str] = None) -> None:
        """
        Thread-safe recording of an execution error.

        Args:
            error_msg: Error message describing the failure.
            log: Optional log message to append.
        """
        with self._lock:
            self.progress_state["status"] = "error"
            self.progress_state["error"] = error_msg
            self.progress_state["completed"] = False
            if log:
                self.progress_state.setdefault("logs", []).append(log)

    def set_completed(
        self,
        status: str,
        confidence: float,
        violations_count: int,
        log: Optional[str] = None,
    ) -> None:
        """
        Thread-safe recording of a successful pipeline run completion.

        Args:
            status: Final decision status ('ACCEPT' or 'REJECT').
            confidence: Overall document confidence score.
            violations_count: Count of detected quality violations.
            log: Optional completion log message.
        """
        with self._lock:
            self.progress_state["status"] = "completed"
            self.progress_state["completed"] = True
            self.progress_state["progress"] = 100
            self.progress_state["step_index"] = 5
            self.progress_state["current_step"] = f"Step 5: Decision Tree Complete ({status})"
            if log:
                self.progress_state.setdefault("logs", []).append(log)

    def set_loaded_run(
        self,
        output_dir: str,
        document_display: str,
        preset: str,
        confidence: Any,
        status: str,
        nodes_count: int,
        violations_count: int,
    ) -> None:
        """
        Sets progress state to reflect an existing run loaded from disk.

        Args:
            output_dir: Output directory loaded.
            document_display: Document path or name for logs.
            preset: Executed preset identifier.
            confidence: Recorded confidence score.
            status: Decision status.
            nodes_count: Count of DOM nodes in result.
            violations_count: Count of quality violations.
        """
        with self._lock:
            self.progress_state = {
                "status": "completed",
                "progress": 100,
                "step_index": 5,
                "current_step": f"Loaded Previous Run ({status})",
                "logs": [
                    f"[LOAD] Successfully loaded previous run artifacts from '{output_dir}'.",
                    (
                        f"[INFO] Document: '{document_display}', Chosen Preset: '{preset}', "
                        f"Confidence: {confidence}, Status: '{status}'."
                    ),
                    f"[INFO] DOM Nodes: {nodes_count}, Quality Violations: {violations_count}.",
                ],
                "completed": True,
                "error": None,
            }
